import requests
import json

class GISAnalyzer:
    def __init__(self):
        self.overpass_url = "https://overpass-api.de/api/interpreter"

    def get_agglomeration_score(self, lat, lon, radius=2000):
        """
        Calculate Agglomeration Score based on nearby firms.
        Complementary firms: shops, crafts, industrial.
        """
        query = f"""
        [out:json][timeout:25];
        (
          node["shop"](around:{radius}, {lat}, {lon});
          node["craft"](around:{radius}, {lat}, {lon});
          node["industrial"](around:{radius}, {lat}, {lon});
        );
        out count;
        """
        try:
            print(f"DEBUG GIS: Querying Overpass for ({lat}, {lon}) radius {radius}")
            response = requests.post(self.overpass_url, data={'data': query}, timeout=30)
            
            if response.status_code != 200:
                print(f"GIS HTTP Error: {response.status_code}")
                return None
                
            data = response.json()
            # Extract count
            elements = data.get('elements', [])
            if not elements:
                print("DEBUG GIS: No elements returned")
                return {'count': 0, 'score': 0, 'area_km2': 0}
                
            count = int(elements[0].get('tags', {}).get('total', 0))
            print(f"DEBUG GIS: Count for ({lat}, {lon}) is {count}")
            
            # Area in km^2 = pi * (radius/1000)^2
            area_km2 = 3.14159 * (radius / 1000)**2
            
            # AI = (Sum Firms) / Area^2
            raw_ai = count / (area_km2 ** 2)
            print(f"DEBUG GIS: Raw AI: {raw_ai}")
            
            # Normalize to 1-100 scale
            # In a city like SF, count is ~270 for 1km. For 2km maybe ~800.
            # 800 / (12.5^2) = 800 / 156 = 5.1
            # We want 5.1 to be ~90. So factor is ~18.
            normalized_score = min(100, int(raw_ai * 15))
            print(f"DEBUG GIS: Final Score: {normalized_score}")
            
            return {
                'count': count,
                'score': normalized_score,
                'area_km2': round(area_km2, 2)
            }
        except Exception as e:
            print(f"GIS Error: {e}")
            return None
