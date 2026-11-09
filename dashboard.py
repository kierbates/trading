import json
from pathlib import Path
import pandas as pd
import streamlit as st
st.set_page_config(page_title='Trading Intelligence',page_icon='📈',layout='wide')
st.title('Trading Intelligence · Paper Trading')
st.caption('Three independent £10,000 virtual portfolios. Daily-bar simulation; not live brokerage execution.')
path=Path(__file__).parent/'data'/'state.json'
if not path.exists():
 st.info('No simulated trading data yet. Run `python engine.py` once, then refresh.');st.stop()
s=json.loads(path.read_text());st.caption(f"Last processed market bar: {s.get('last_bar','none')} · Updated: {s.get('updated_utc','not yet')}")
accounts=s['accounts'];cols=st.columns(3)
for col,(name,a) in zip(cols,accounts.items()):
 value=a['equity'][-1]['value_gbp'] if a['equity'] else 10000
 col.metric(name,f'£{value:,.2f}',f'{(value/10000-1)*100:+.2f}%')
chart=[]
for name,a in accounts.items():
 for item in a['equity']:chart.append({'date':item['date'],'strategy':name,'balance':item['value_gbp']})
if chart:
 df=pd.DataFrame(chart);df['date']=pd.to_datetime(df['date'])
 st.subheader('Portfolio values (GBP)');st.line_chart(df.pivot(index='date',columns='strategy',values='balance'))
for name,a in accounts.items():
 with st.expander(f'{name}: positions, orders and trade history',expanded=False):
  st.write('Cash:',f"£{a['cash_gbp']:,.2f}")
  st.write('Positions:',a['positions'] or 'None')
  st.write('Queued for next market open:',a['pending'] or 'None')
  trades=pd.DataFrame(a['trades'])
  if not trades.empty:
   st.dataframe(trades.iloc[::-1],use_container_width=True)
   st.download_button('Download trades CSV',trades.to_csv(index=False),file_name=f'{name.lower()}_trades.csv')
  else:st.write('No trades yet')
st.warning('Paper fills use daily opening prices, assumed costs and approximate FX conversion. Real fills, slippage, market gaps and currency conversion can differ materially. This is not a validated profitable strategy.')
