import pandas as pd
import altair as alt
from datetime import datetime
import sys
from google.cloud import storage
import os


def volt_vs_spot(option_type, asset, save_img=False):

    # construct price dataframe
    df_price_file_index = pd.read_json('https://storage.googleapis.com/friktion-reference-files/asset_prices.json')
    try:
        df_prices = pd.read_json(df_price_file_index[df_price_file_index['asset'] == asset.upper()]['url'].iloc[0])
    except:
        sys.exit('The asset you selected is not currently being tracked.')

    df_prices.rename(columns={
        0:'unix_time',
        1:'price'
    },inplace=True)

    df_prices['date'] = df_prices['unix_time'].apply(lambda x: datetime.fromtimestamp(x/1000))


    # construct share token price dataframe
    url = 'https://raw.githubusercontent.com/Friktion-Labs/mainnet-tvl-snapshots/main/derived_timeseries/mainnet_income_{}_{}_sharePricesByGlobalId.json'.format(option_type, asset)

    try:
        df_share_token_price = pd.read_json(url)
    except:
        sys.exit('This file does not exist.')

    df_share_token_price.rename(columns={
        0:'unix_time',
        1:'share_token_price'
    },inplace=True)

    df_share_token_price['date'] = df_share_token_price['unix_time'].apply(lambda x: datetime.fromtimestamp(x/1000))
    df_share_token_price['growth'] = df_share_token_price['share_token_price'] / 1.0 - 1


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
        title=asset.upper()+' '+option_type+' Position vs. Spot Price'
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
            title=asset.upper()+' '+option_type.capitalize()+' Position vs. Spot Price'
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

        blob = bucket.blob('spot-vs-portfolio-value/'+asset+'-'+option_type+'/'+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        blob.upload_from_filename('tmp/'+datetime.now().strftime('%Y-%m-%dT%H:%M:%S')+'.png')
        print('uploaded file to google cloud storage')