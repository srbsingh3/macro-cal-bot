import requests
import json

# Load config
with open('config.json') as f:
    config = json.load(f)

api_key = config['api_ninjas']['api_key']
food_name = "banana"  # Test with a simple food item

api_url = f'https://api.api-ninjas.com/v1/nutrition?query={food_name}'
headers = {
    'X-Api-Key': api_key
}

try:
    response = requests.get(api_url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json() if response.ok else response.text}")
except Exception as e:
    print(f"Error: {str(e)}") 