import pandas as pd
import altair as alt
from datetime import datetime
import sys
from google.cloud import storage
import os
import requests
import json
import ccxt
import numpy as np



def volt_vs_spot(option_type, deposited_asset, save_img=False, save_img_dir=None):
    '''A function that pulls the historical spot price of an underlying asset and the historical performance of a volt, and renders a chart to show cumulative performance.'''

    # create mainnet volts reference dataframe
    if option_type == 'call':
        volt_type = 1
    elif option_type == 'put':
        volt_type = 2
    
    reference_url = 'https://raw.githubusercontent.com/Friktion-Labs/mainnet-tvl-snapshots/main/friktionSnapshot.json'
    response = requests.get(reference_url)
    data = response.json()
    df_general_reference = pd.DataFrame(data['allMainnetVolts'])
    df_asset_reference = df_general_reference[
        (df_general_reference['voltType'] == volt_type) &
        (df_general_reference['depositTokenSymbol'].lower() == deposited_asset.lower())
        ]


    # construct price dataframe
    if df_asset_reference['globalId'].iloc[0] in ['mainnet_income_put_pai','mainnet_income_put_tsUSDC','mainnet_income_put_uxd','mainnet_income_put_sol','mainnet_income_put_sol_high']:
        globalId_mod = 'mainnet_income_call_sol'
    elif 'put' in df_asset_reference['globalId'].iloc[0]:
        globalId_mod = df_asset_reference['globalId'].iloc[0].replace('put','call')
    else:
        globalId_mod = df_asset_reference['globalId'].iloc[0]
    
    try:
        df_prices = pd.read_json('https://raw.githubusercontent.com/Friktion-Labs/mainnet-tvl-snapshots/main/derived_timeseries/{}_pricesByCoingeckoId.json'.format(globalId_mod))
    except:
        sys.exit('The asset you selected is not currently being tracked.')

    df_prices.rename(columns={
        0:'unix_time',
        1:'price'
    },inplace=True)

    df_prices['date'] = df_prices['unix_time'].apply(lambda x: datetime.fromtimestamp(x/1000))


    # construct share token price dataframe
    share_token_url = 'https://raw.githubusercontent.com/Friktion-Labs/mainnet-tvl-snapshots/main/derived_timeseries/{}_sharePricesByGlobalId.json'.format(df_asset_reference['globalId'].iloc[0])

    try:
        df_share_token_price = pd.read_json(share_token_url)
    except:
        sys.exit('This file does not exist.')

    df_share_token_price.rename(columns={
        0:'unix_time',
        1:'share_token_price'
    },inplace=True)

    df_share_token_price['date'] = df_share_token_price['unix_time'].apply(lambda x: datetime.fromtimestamp(x/1000))
    df_share_token_price['growth'] = df_share_token_price['share_token_price'] / 1.0 - 1


    # create chart title variables
    asset = df_asset_reference['depositTokenSymbol'].iloc[0]


    if df_asset_reference['isVoltage'].iloc[0]:
        voltage = '-High'
    else:
        voltage = ''


    # create charts
    alt.data_transformers.disable_max_rows()

    share_token_chart = alt.Chart(df_share_token_price).mark_line().encode(
        x=alt.X(
            'yearmonthdate(date)',
            axis=alt.Axis(
                title='',
                labelAngle=-45
            )
        ),
        y=alt.Y(
            'growth',
            axis=alt.Axis(
                title='Portfolio Value',
                format='.1%'
            )
        )
    ).properties(
        width=600,
        title=asset+voltage+' '+option_type.capitalize()+' Position vs. Spot Price'
    )


    if df_prices['price'].min() < 1:
        format = '$,.2f'
    else:
        format = '$,.0f'

    spot_price_chart = alt.Chart(df_prices[
        (df_prices['date'] >= df_share_token_price['date'].min()) &
        (df_prices['date'] <= df_share_token_price['date'].max())
    ]
        ).mark_line(opacity=0.50).encode(
            x=alt.X(
                'yearmonthdate(date)',
                axis=alt.Axis(
                    title='',
                    labelAngle=-45
                )
            ),
            y=alt.Y(
                'price',
                axis=alt.Axis(
                    title='Price',
                    format=format
                ),
                scale=alt.Scale(domain=[df_prices['price'].min(),df_prices['price'].max()])
            ),
            color=alt.value('goldenrod')
        ).properties(
            width=600,
            title=asset+voltage+' '+option_type.capitalize()+' Position vs. Spot Price'
        )

    final_chart = (spot_price_chart + share_token_chart).resolve_scale(y='independent')

    if not save_img:
        return final_chart
    
    elif save_img:
        client = storage.Client()
        bucket = client.get_bucket('zaps')
        print('established cloud resource client')

        final_chart.save('./tmp/'+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        print('saved chart image')

        blob = bucket.blob('spot-vs-portfolio-value/'+globalId+'/'+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        blob.upload_from_filename(save_img_dir+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        print('uploaded file to google cloud storage')

        os.remove(save_img_dir+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        print('removed file from local storage')


def realized_volatility(ftx_api_key, ftx_secret):
    pass