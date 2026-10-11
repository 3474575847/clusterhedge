import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import pearsonr
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from datetime import datetime, timedelta

class MaterialCorrelationEngine:
    def __init__(self, config):
        self.config = config
        self.material_tickers = config.MATERIAL_TICKERS
        self.proxy_etfs = config.PROXY_ETFS

    def get_historical_data(self, ticker, period="1y"):
        """Fetch historical close prices for a ticker."""
        try:
            data = yf.download(ticker, period=period, interval="1d", progress=False)
            if data.empty:
                return None
            return data['Close']
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None

    def calculate_correlation(self, material_name, period="1y"):
        """
        Calculate Pearson correlation between a material's proxy ticker 
        and a set of commodity-linked ETFs.
        """
        material_ticker = self.material_tickers.get(material_name.lower())
        if not material_ticker:
            return None, "Material ticker mapping not found."

        material_data = self.get_historical_data(material_ticker, period)
        if material_data is None:
            print(f"DEBUG: Material data for {material_ticker} is None")
            return None, f"Could not fetch data for material ticker {material_ticker}."

        print(f"DEBUG: Found {len(material_data)} points for {material_ticker}")
        results = []
        for etf in self.proxy_etfs:
            print(f"DEBUG: Fetching ETF {etf}")
            etf_data = self.get_historical_data(etf, period)
            if etf_data is None:
                print(f"DEBUG: ETF data for {etf} is None")
                continue

            # Align the two series
            combined = pd.concat([material_data, etf_data], axis=1).dropna()
            combined.columns = ['Material', 'ETF']
            
            print(f"DEBUG: Combined {etf} has {len(combined)} overlapping points")
            if len(combined) < 5: # Lowered for debugging
                continue

            # Cointegration Test (Engle-Granger)
            _, p_value, _ = coint(combined['Material'], combined['ETF'])
            is_cointegrated = p_value < 0.05

            # Johansen Cointegration Test
            # det_order=0 (constant), k_ar_diff=1 (lag)
            johansen_res = coint_johansen(combined, det_order=0, k_ar_diff=1)
            # Trace statistic for rank=0 vs rank=1
            trace_stat = johansen_res.lr1[0]
            trace_crit = johansen_res.cvt[0, 1] # 95% critical value
            is_johansen = trace_stat > trace_crit

            # ADF Test for Stationarity (Unit Root)
            adf_p_material = adfuller(combined['Material'])[1]

            # VECM Alpha (Mean Reversion Speed) Approximation
            # Delta_Y = Alpha (Y_t-1 - Beta X_t-1) + ...
            # We approximate Alpha by regressing the error term on its change
            error = combined['Material'] - combined['ETF']
            error_lag = error.shift(1).dropna()
            error_diff = error.diff().dropna()
            
            # Simple regression for Alpha: diff = alpha * lag
            # A negative alpha indicates mean reversion. Magnitude is speed.
            from scipy.stats import linregress
            reg = linregress(error_lag.values, error_diff.values)
            mean_reversion_speed = -reg.slope if reg.pvalue < 0.05 else 0

            correlation, _ = pearsonr(combined['Material'], combined['ETF'])
            results.append({
                'ticker': etf,
                'correlation': float(correlation),
                'p_value_coint': float(p_value),
                'is_cointegrated': bool(is_cointegrated),
                'is_johansen': bool(is_johansen),
                'adf_p': float(adf_p_material),
                'mean_reversion_speed': float(mean_reversion_speed),
                'data_points': len(combined)
            })

        # Sort by correlation descending
        results = sorted(results, key=lambda x: x['correlation'], reverse=True)
        return results, None

    def suggest_hedge(self, material_name, exposure_amount, adjusted_returns=None):
        """
        Suggest a hedge ticker and amount based on correlation.
        Optional: Factor in adjusted_returns (Black-Litterman Posterior).
        """
        correlations, error = self.calculate_correlation(material_name)
        if error or not correlations:
            return None, error

        top_hedge = correlations[0]
        # In a real scenario, we'd also consider volatility (Beta)
        # For MVP, we suggest hedge amount = exposure * correlation
        base_amount = exposure_amount * top_hedge['correlation']
        
        # Apply Subjective Alpha Adjustment if available
        alpha_adj = 0
        if adjusted_returns and top_hedge['ticker'] in adjusted_returns:
            alpha_adj = adjusted_returns[top_hedge['ticker']]
        
        # The hedge amount increases if we expect a price spike
        suggested_amount = base_amount * (1 + alpha_adj)
        
        # Institutional Hedge Confidence Score
        # 100 base. -20 if no cointegration. Scaled by correlation.
        confidence_score = top_hedge['correlation'] * 100
        if not top_hedge['is_cointegrated']:
            confidence_score *= 0.6 # Significant penalty for spurious correlation
        
        return {
            'material': material_name,
            'recommended_ticker': top_hedge['ticker'],
            'correlation': top_hedge['correlation'],
            'is_cointegrated': top_hedge['is_cointegrated'],
            'is_johansen': top_hedge['is_johansen'],
            'adf_p': top_hedge['adf_p'],
            'mean_reversion_speed': top_hedge['mean_reversion_speed'],
            'confidence_score': round(confidence_score, 1),
            'base_hedge_value': round(base_amount, 2),
            'suggested_hedge_value': round(suggested_amount, 2),
            'alpha_impact': round(alpha_adj * 100, 2)
        }, None
