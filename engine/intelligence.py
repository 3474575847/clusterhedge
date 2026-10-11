class InsightEngine:
    def __init__(self):
        pass

    def get_pivot_suggestions(self, project, simulations):
        """
        Generate strategic advice based on project data and simulations.
        """
        suggestions = []
        
        # 1. Volatility check
        if simulations.get('mean_cost', 0) > 0:
            risk_buffer = simulations['var_95'] - simulations['mean_cost']
            if risk_buffer / simulations['mean_cost'] > 0.1:
                suggestions.append({
                    'type': 'risk',
                    'title': 'High Volatility Detected',
                    'body': 'Your material costs are highly volatile. Consider increasing your proxy hedge to 110% of exposure.'
                })
        
        # 2. Agglomeration check
        if project.agglomeration_score and project.agglomeration_score > 70:
            suggestions.append({
                'type': 'alpha',
                'title': 'High Agglomeration Alpha',
                'body': 'Your local economic cluster is dense. You have significant pricing power—consider a 15-20% retail premium.'
            })
        elif project.agglomeration_score and project.agglomeration_score < 30:
            suggestions.append({
                'type': 'alpha',
                'title': 'Low Local Density',
                'body': 'Limited local clustering. Focus on online sales or cost-cutting rather than high retail premiums.'
            })

        # 3. Correlation check (Mock check for MVP)
        # In a real app we'd check if MCE found a good match
        if not project.hedge_recommendations:
             suggestions.append({
                'type': 'action',
                'title': 'Unprotected Exposure',
                'body': 'No hedges active. Run Quant Analysis to protect your margins.'
            })

        # Default suggestion
        if not suggestions:
            suggestions.append({
                'type': 'info',
                'title': 'Stability Optimizing',
                'body': 'Project parameters are within normal variance. Maintain current supply chain.'
            })

        return suggestions
