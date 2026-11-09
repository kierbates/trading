"""Daily-bar virtual trading competition. No broker orders, no real money."""
import json, os, math
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf

ROOT=Path(__file__).resolve().parent
STATE=ROOT/'data'/'state.json'
SYMBOLS=['SPY','QQQ','IWM','GLD','TLT','XLE']
CONFIG={
 'Conservative': {'risk':.003,'max_positions':2,'allocation':.35,'stop':.035,'take':.09,'fast':20,'slow':80,'breakout':30,'daily_limit':.012},
 'Active': {'risk':.005,'max_positions':3,'allocation':.40,'stop':.045,'take':.10,'fast':10,'slow':40,'breakout':15,'daily_limit':.02},
 'Aggressive': {'risk':.008,'max_positions':3,'allocation':.50,'stop':.065,'take':.15,'fast':5,'slow':20,'breakout':8,'daily_limit':.03},
}
SLIPPAGE=.0005  # 5 basis points each execution, illustrative
FEE_GBP=0.25  # assumed per order; change to model actual broker costs

def load_prices():
    prices={}
    for symbol in SYMBOLS+['GBPUSD=X']:
        df=yf.download(symbol,period='18mo',interval='1d',auto_adjust=True,progress=False,threads=False)
        if df.empty: raise RuntimeError(f'No price data for {symbol}; refusing to trade')
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        df=df[['Open','High','Low','Close']].dropna().copy()
        df.index=pd.to_datetime(df.index).tz_localize(None).normalize()
        prices[symbol]=df
    return prices

def new_state():
    return {'created_utc':datetime.now(timezone.utc).isoformat(),'last_bar':None,
      'accounts':{name:{'cash_gbp':10000.,'positions':{},'trades':[],'equity':[],'pending':[], 'halted_day':None} for name in CONFIG}}

def load_state():
    if STATE.exists(): return json.loads(STATE.read_text())
    return new_state()

def save_state(state):
    STATE.parent.mkdir(exist_ok=True)
    tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2,allow_nan=False));os.replace(tmp,STATE)

def gbp_price(usd,gbpusd): return float(usd)/float(gbpusd)

def equity(acct, date, prices, fx):
    total=acct['cash_gbp']
    for symbol,pos in acct['positions'].items():
        frame=prices[symbol].loc[:date]
        if not frame.empty: total+=pos['qty']*gbp_price(frame.iloc[-1]['Close'],fx)
    return total

def signal(df, cfg, date):
    past=df.loc[:date]
    if len(past)<cfg['slow']+cfg['breakout']+2:return False
    c=past['Close']; fast=c.rolling(cfg['fast']).mean().iloc[-1];slow=c.rolling(cfg['slow']).mean().iloc[-1]
    prior_high=past['High'].shift(1).rolling(cfg['breakout']).max().iloc[-1]
    return bool(c.iloc[-1]>fast>slow and c.iloc[-1]>prior_high)

def run():
    prices=load_prices(); state=load_state()
    # Only bars common to all instruments; avoids accidental future FX use.
    dates=sorted(set.intersection(*(set(df.index) for df in prices.values())))
    if len(dates)<100:raise RuntimeError('Insufficient aligned market history')
    # Only act on the latest available complete daily bar, never retroactively replay months.
    today=dates[-1]; key=today.strftime('%Y-%m-%d')
    if state['last_bar']==key: print('Already processed',key);return
    previous=dates[-2]; fx_open=float(prices['GBPUSD=X'].loc[today,'Open']);fx_close=float(prices['GBPUSD=X'].loc[today,'Close'])
    for name,cfg in CONFIG.items():
        a=state['accounts'][name]
        # Execute pending orders generated at the previous close, at today's open.
        for order in a['pending']:
            sym=order['symbol']; p=gbp_price(prices[sym].loc[today,'Open'],fx_open)
            if order['side']=='buy':
                if sym in a['positions']:continue
                available_equity=equity(a,previous,prices,float(prices['GBPUSD=X'].loc[previous,'Close']))
                risk_cash=available_equity*cfg['risk']
                qty=min(math.floor(risk_cash/(p*cfg['stop'])),math.floor(available_equity*cfg['allocation']/p),math.floor(max(0,a['cash_gbp']-FEE_GBP)/(p*(1+SLIPPAGE))))
                if qty<1:continue
                execution=p*(1+SLIPPAGE); cost=qty*execution+FEE_GBP
                if cost>a['cash_gbp']:continue
                a['cash_gbp']-=cost
                a['positions'][sym]={'qty':qty,'entry':execution,'entry_date':key,'stop':execution*(1-cfg['stop']),'take':execution*(1+cfg['take']),'entry_fee':FEE_GBP}
                a['trades'].append({'date':key,'symbol':sym,'side':'BUY','qty':qty,'price_gbp':round(execution,5),'fee_gbp':FEE_GBP,'realized_pnl_gbp':None})
            elif order['side']=='sell' and sym in a['positions']:
                pos=a['positions'].pop(sym);execution=p*(1-SLIPPAGE)
                proceeds=pos['qty']*execution-FEE_GBP;a['cash_gbp']+=proceeds
                pnl=pos['qty']*(execution-pos['entry'])-FEE_GBP-pos['entry_fee']
                a['trades'].append({'date':key,'symbol':sym,'side':'SELL','qty':pos['qty'],'price_gbp':round(execution,5),'fee_gbp':FEE_GBP,'realized_pnl_gbp':round(pnl,2)})
        a['pending']=[]
        eq=equity(a,today,prices,fx_close)
        a['equity'].append({'date':key,'value_gbp':round(eq,2)})
        # Daily circuit breaker based on previous recorded equity; no new positions when tripped.
        prior_eq=a['equity'][-2]['value_gbp'] if len(a['equity'])>1 else 10000.
        circuit=eq < prior_eq*(1-cfg['daily_limit'])
        if circuit:a['halted_day']=key
        # Exit signals are placed for NEXT market open; stops are close-based, not guaranteed fills.
        for sym,pos in a['positions'].items():
            close=gbp_price(prices[sym].loc[today,'Close'],fx_close)
            if close<=pos['stop'] or close>=pos['take'] or circuit or close<prices[sym].loc[:today,'Close'].tail(cfg['fast']).mean()/fx_close:
                a['pending'].append({'side':'sell','symbol':sym})
        if not circuit:
            occupied=set(a['positions'])
            slots=max(0,cfg['max_positions']-len(occupied))
            for sym in SYMBOLS:
                if slots==0:break
                if sym not in occupied and signal(prices[sym],cfg,today):
                    a['pending'].append({'side':'buy','symbol':sym});slots-=1
    state['last_bar']=key;state['updated_utc']=datetime.now(timezone.utc).isoformat();save_state(state)
    print('Processed',key)

if __name__=='__main__':run()
