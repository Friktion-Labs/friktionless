import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import sys
from google.cloud import storage
import os
import requests
import json
import ccxt
import numpy as np
import re



def volt_vs_spot(option_type, deposited_asset, underlying_asset, isHighVoltage=False, save_img=False, save_img_dir=None):
    '''A function that pulls the historical spot price of an underlying asset and the historical performance of a volt, and renders a chart to show cumulative performance.'''

    # create mainnet volts reference dataframe
    if option_type.lower() == 'call':
        volt_type = 1
    elif option_type.lower() == 'put':
        volt_type = 2
    
    reference_url = 'https://raw.githubusercontent.com/Friktion-Labs/mainnet-tvl-snapshots/main/friktionSnapshot.json'
    response = requests.get(reference_url)
    data = response.json()
    df_general_reference = pd.DataFrame(data['allMainnetVolts'])
    df_asset_reference = df_general_reference[
        (df_general_reference['voltType'] == volt_type) &
        (df_general_reference['depositTokenSymbol'].str.lower() == deposited_asset.lower()) &
        (df_general_reference['underlyingTokenSymbol'].str.lower() == underlying_asset.lower()) &
        (df_general_reference['isVoltage'] == isHighVoltage)
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


def realized_volatility(
    ftx_api_key, 
    ftx_secret, 
    asset_pairs, 
    price_window_size='5m', 
    reference_time=datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), 
    lookback_days=7
    ):

    cftx = ccxt.ftx(
    {"apiKey" : ftx_api_key,
     "secret" : ftx_secret
     }
    )

    time_since = datetime.timestamp(datetime.strptime(reference_time,'%Y-%m-%dT%H:%M:%S') - timedelta(days=lookback_days))*1000

    if not isinstance(asset_pairs, list):
        asset_pairs = [asset_pairs]

    
    if re.findall('[a-z]', price_window_size)[0] == 'm':
        multiplier = 1440 / int(re.findall('[0-9]+', price_window_size)[0])
    elif re.findall('[a-z]', price_window_size)[0] == 'h':
        multiplier = 24 / int(re.findall('[0-9]+', price_window_size)[0])
    elif re.findall('[a-z]', price_window_size)[0] == 'd':
        multiplier = 1

    data_dict = {}

    for asset_pair in asset_pairs:
        data = cftx.fetchOHLCV(asset_pair, price_window_size, since=time_since, limit=int(lookback_days*multiplier))
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume"])
        data_dict[asset_pair] = df
    
    asset_dict = {
    'asset_pair' : [],
    'high' : [],
    'low' : [],
    'mean' : [],
    'close' : [],
    'range' : [],
    'realized_volatility_'+str(lookback_days)+'d' : []
    }

    for k, v in data_dict.items():
        v["vol"] = np.log(v.high/v.low)**2
        
        asset_dict['asset_pair'].append(k)
        asset_dict['high'].append(v['close'].max())
        asset_dict['low'].append(v['close'].min())
        asset_dict['mean'].append(v['close'].mean())
        asset_dict['close'].append(v['close'].iloc[0])
        asset_dict['range'].append(str(100*(v.close.max()-v.close.min())/v.close.iloc[0]))
        asset_dict['realized_volatility_'+str(lookback_days)+'d'].append(str(np.sqrt(v.vol.sum()*1/(4*10*np.log(2)))*np.sqrt(365)*100))
    
    return pd.DataFrame(asset_dict)
    