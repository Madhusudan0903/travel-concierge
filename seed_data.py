import os
from google.cloud import firestore

# Hardcode project ID to avoid project number issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-01-057ee13d7fba"

def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)

def seed_firestore():
    db = get_firestore_client()
    collection_name = "destinations"

    sample_destinations = [
        {
            "id": "dest-tokyo-01",
            "name": "Historic Asakusa & Culinary Tour",
            "city": "Tokyo",
            "country": "Japan",
            "category": "Culinary & Culture",
            "description": "Explore ancient Senso-ji temple, traditional izakayas, and world-class ramen alleyways.",
            "avg_cost_per_day": 180,
            "best_season": "Spring (Cherry Blossom) & Autumn",
            "rating": 4.9
        },
        {
            "id": "dest-kyoto-02",
            "name": "Arashiyama Bamboo Grove & Zen Gardens",
            "city": "Kyoto",
            "country": "Japan",
            "category": "Culture & Nature",
            "description": "Walk through serene bamboo paths, historic temples, and traditional tea houses.",
            "avg_cost_per_day": 150,
            "best_season": "Autumn & Spring",
            "rating": 4.8
        },
        {
            "id": "dest-paris-01",
            "name": "Montmartre Art & Bakery Walk",
            "city": "Paris",
            "country": "France",
            "category": "Culinary & Art",
            "description": "Charming cobblestone streets, Sacré-Cœur views, artisan boulangeries, and bistro dining.",
            "avg_cost_per_day": 220,
            "best_season": "Spring & Summer",
            "rating": 4.7
        },
        {
            "id": "dest-bali-01",
            "name": "Ubud Rainforest & Wellness Retreat",
            "city": "Ubud",
            "country": "Indonesia",
            "category": "Wellness & Nature",
            "description": "Lush rice terraces, yoga sanctuaries, organic dining, and traditional Balinese spa treatments.",
            "avg_cost_per_day": 90,
            "best_season": "Dry Season (April - October)",
            "rating": 4.9
        },
        {
            "id": "dest-sf-01",
            "name": "San Francisco Bay & Coastal Hike",
            "city": "San Francisco",
            "country": "USA",
            "category": "Adventure & Coastal",
            "description": "Golden Gate views, Lands End coastal trails, seafood at Fisherman's Wharf, and cable car rides.",
            "avg_cost_per_day": 250,
            "best_season": "Autumn (September - November)",
            "rating": 4.6
        }
    ]

    print(f"Seeding Firestore collection '{collection_name}' in project '{PROJECT_ID}'...")
    for item in sample_destinations:
        doc_ref = db.collection(collection_name).document(item["id"])
        doc_ref.set(item)
        print(f"  ✓ Added: {item['name']} ({item['city']}, {item['country']})")

    print(f"Successfully seeded {len(sample_destinations)} items into Firestore!")

if __name__ == "__main__":
    seed_firestore()
