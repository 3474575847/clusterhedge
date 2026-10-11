import numpy as np

class BlackLittermanEngine:
    def __init__(self, tau=0.05):
        """
        tau: scalar indicating the uncertainty of the prior (usually 0.02 - 0.05).
        """
        self.tau = tau

    def calculate_posterior(self, tickers, correlations_matrix, market_priors, views):
        """
        tickers: list of ticker strings
        correlations_matrix: NxN numpy array of historical correlations
        market_priors: dict {ticker: expected_return}
        views: list of dicts {'ticker': str, 'prediction': float, 'confidence': float} (confidence 1-10)
        """
        n = len(tickers)
        if n == 0:
            return {}

        # 1. Prepare Pi (Market Equilibrium Returns)
        Pi = np.array([market_priors.get(t, 0.0) for t in tickers])

        # 2. Prepare Sigma (Prior Covariance Matrix)
        # For MVP, we treat correlations as a proxy for covariance by assuming unit variance
        # A better version would factor in historical volatilities
        Sigma = correlations_matrix

        # 3. Prepare P, Q, and Omega (User Views)
        if not views:
            return market_priors

        v = len(views)
        P = np.zeros((v, n))
        Q = np.zeros(v)
        Omega = np.zeros((v, v))

        ticker_to_idx = {t: i for i, t in enumerate(tickers)}

        for i, view in enumerate(views):
            ticker = view['ticker']
            if ticker in ticker_to_idx:
                idx = ticker_to_idx[ticker]
                P[i, idx] = 1
                Q[i] = view['prediction']
                
                # Confidence 1-10 mapped to uncertainty
                # High confidence (10) -> Low variance (Omega is small)
                # Low confidence (1) -> High variance (Omega is large)
                # Formula: Omega_ii = p_i * Sigma * p_i^T * (1-conf)/conf
                conf = view['confidence'] / 10.0
                if conf <= 0: conf = 0.01
                
                # Simplified uncertainty calculation
                uncertainty = (1.0 - conf) / (conf + 0.00001)
                Omega[i, i] = uncertainty * (P[i] @ Sigma @ P[i].T)

        # 4. Black-Litterman Formula (Posterior Expected Returns)
        # mu = Pi + tau * Sigma * P.T * inv(P * tau * Sigma * P.T + Omega) * (Q - P * Pi)
        
        try:
            tau_sigma_P_T = self.tau * Sigma @ P.T
            middle_inv = np.linalg.inv(P @ (self.tau * Sigma) @ P.T + Omega)
            
            mu = Pi + tau_sigma_P_T @ middle_inv @ (Q - P @ Pi)
            
            return {tickers[i]: float(mu[i]) for i in range(n)}
        except Exception as e:
            print(f"BL Calculation Error: {e}")
            return market_priors

if __name__ == '__main__':
    # Standalone test for Black-Litterman logic
    print("Testing Black-Litterman Engine...")
    bl = BlackLittermanEngine()
    
    # Mock data
    test_tickers = ['CPER', 'WOOD', 'SLX']
    # Mock identity correlation matrix
    test_matrix = np.eye(3) 
    test_priors = {'CPER': 0.0, 'WOOD': 0.0, 'SLX': 0.0}
    
    test_views = [
        {'ticker': 'CPER', 'prediction': 0.15, 'confidence': 8},
        {'ticker': 'WOOD', 'prediction': -0.05, 'confidence': 5}
    ]
    
    posteriors = bl.calculate_posterior(test_tickers, test_matrix, test_priors, test_views)
    print("Market Priors:", test_priors)
    print("User Views:", test_views)
    print("Resulting Posteriors (Alpha):", posteriors)
