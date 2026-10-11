import pandas as pd
import numpy as np
import yfinance as yf
from scipy.optimize import minimize

class BacktesterEngine:
    def __init__(self, config):
        self.config = config

    def run_backtest(self, material_ticker, hedge_ticker, start_date="2021-01-01", end_date=None):
        """
        Compare Unhedged vs Hedged portfolio performance.
        Returns metrics and a plot-ready data series.
        """
        if not end_date:
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            
        try:
            # Fetch historical data
            m_data = yf.download(material_ticker, start=start_date, end=end_date, progress=False)['Close']
            h_data = yf.download(hedge_ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if m_data.empty or h_data.empty:
                return None, "Insufficient historical data."
                
            # Align and calculate daily returns
            combined = pd.concat([m_data, h_data], axis=1).dropna()
            combined.columns = ['Material', 'Hedge']
            
            # Normalize to 100 for comparison
            combined['Unhedged_Price'] = (combined['Material'] / combined['Material'].iloc[0]) * 100
            
            # Calculate returns
            m_returns = combined['Material'].pct_change().dropna()
            h_returns = combined['Hedge'].pct_change().dropna()
            
            # Simple Hedge Ratio (1:1 for MVP, could be optimized via Beta)
            # Port_Returns = Material_Returns - Hedge_Returns
            # (Assuming we go long material and buy a put/short the hedge, 
            # or go long the material and long the hedge to offset cost increases)
            # In our context, hedging is about offsetting cost spikes.
            # So Hedged_Return = Material_Return - Hedge_Return (cost perspective)
            
            combined['Hedged_Returns'] = m_returns - h_returns
            combined['Hedged_Price'] = 100 * (1 + combined['Hedged_Returns']).cumprod()
            # Ensure index 0 starts at 100
            combined.loc[combined.index[0], 'Hedged_Price'] = 100
            combined['Hedged_Price'] = combined['Hedged_Price'].ffill().fillna(100)
            
            # Metrics
            unhedged_vol = m_returns.std() * np.sqrt(252)
            hedged_vol = combined['Hedged_Returns'].std() * np.sqrt(252)
            vol_reduction = (unhedged_vol - hedged_vol) / unhedged_vol * 100
            
            # Sharpe Ratio (Assuming 0% risk-free rate for simplicity)
            sharpe = (combined['Hedged_Returns'].mean() / combined['Hedged_Returns'].std()) * np.sqrt(252)
            
            # Maximum Drawdown
            # Rolling peak
            peak = combined['Hedged_Price'].expanding(min_periods=1).max()
            drawdown = (combined['Hedged_Price'] - peak) / peak
            max_drawdown = drawdown.min() * 100

            return {
                'metrics': {
                    'unhedged_vol': round(unhedged_vol, 4),
                    'hedged_vol': round(hedged_vol, 4),
                    'vol_reduction': round(vol_reduction, 2),
                    'sharpe': round(sharpe, 2),
                    'max_drawdown': round(max_drawdown, 2)
                },
                'timeseries': combined[['Unhedged_Price', 'Hedged_Price']].reset_index().to_dict('records')
            }, None

            
        except Exception as e:
            return None, str(e)
class RiskManager:
    def __init__(self, config):
        self.config = config

    def run_monte_carlo(self, materials, n_simulations=1000, days=30):
        """
        Run a Monte Carlo simulation on a bill of materials to estimate VaR.
        """
        total_initial_cost = sum(m['exposure'] for m in materials)
        if total_initial_cost == 0:
            return {'mean_cost': 0, 'var_95': 0}

        # Mock daily volatility for common materials (in a real app, fetch from yfinance)
        vols = {
            'copper': 0.02,
            'steel': 0.015,
            'lumber': 0.03,
            'aluminum': 0.018,
            'plastic': 0.01
        }

        simulated_final_costs = []

        for _ in range(n_simulations):
            iteration_cost = 0
            for m in materials:
                m_name = m['name'].lower()
                # Find matching vol
                vol = 0.02 # Default 2% daily
                for k, v in vols.items():
                    if k in m_name:
                        vol = v
                        break
                
                # Geometric Brownian Motion simulation for 'days'
                daily_returns = np.random.normal(0, vol, days)
                price_multiplier = np.exp(np.sum(daily_returns))
                iteration_cost += m['exposure'] * price_multiplier
            
            simulated_final_costs.append(iteration_cost)

        mean_cost = np.mean(simulated_final_costs)
        var_95 = np.percentile(simulated_final_costs, 95)

        return {
            'mean_cost': round(float(mean_cost), 2),
            'var_95': round(float(var_95), 2),
            'expected_increase': round(float(var_95 - total_initial_cost), 2)
        }
