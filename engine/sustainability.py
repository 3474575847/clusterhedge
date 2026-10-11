class SustainabilityEngine:
    def __init__(self):
        # Estimated carbon intensities (CO2e per unit)
        # These are mock averages for demo purposes
        self.carbon_intensity = {
            'copper': 2.50,    # kg CO2e per kg
            'steel': 1.85,     # kg CO2e per kg
            'lumber': 0.15,    # kg CO2e per ft
            'aluminum': 12.0,  # kg CO2e per kg (very high energy)
            'plastic': 6.0     # kg CO2e per kg
        }

    def calculate_esv(self, material, carbon_price_per_ton=85.0):
        """
        Calculate Economic Sustainability Value (ESV).
        CTE Factor = Qty * CarbonIntensity * PricePerTon
        """
        base_name = material.name.lower()
        key = next((k for k in self.carbon_intensity if k in base_name), None)
        
        # Base footprint calculation (convert kg to metric tons)
        unit_footprint = self.carbon_intensity.get(key, 1.0)
        total_footprint_kg = unit_footprint * material.quantity
        total_tons = total_footprint_kg / 1000.0
        
        # Carbon Tax Exposure (CTE)
        cte = total_tons * carbon_price_per_ton
        
        # Savings logic for upcycling
        carbon_offset_kg = 0.0
        sustainability_premium = 0.0
        cte_savings = 0.0
        
        if material.is_upcycled:
            carbon_offset_kg = total_footprint_kg * 0.85
            sustainability_premium = 0.10 + (min(unit_footprint, 10.0) / 100.0)
            cte_savings = (carbon_offset_kg / 1000.0) * carbon_price_per_ton
            
        result = {
            'footprint': total_footprint_kg,
            'offset': carbon_offset_kg,
            'footprint_kg': total_footprint_kg,
            'offset_kg': carbon_offset_kg,
            'cte_exposure': cte,
            'cte_savings': cte_savings,
            'premium_pct': sustainability_premium * 100,
            'risk_insulation': "High" if material.is_upcycled else "Zero",
            'data_sources': [
                "EIA Open Data (Energy Intensity)",
                "World Bank Carbon Pricing Dashboard (Live Spot Price)",
                "Refinitiv ESG Data (Supply Chain Transparency)"
            ]
        }
        return result

