import json
import os
import requests
from google.cloud import vision
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
from datetime import datetime
from supabase import create_client

# Load environment variables
load_dotenv()

# Replace config loading with environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_NINJAS_KEY = os.getenv('API_NINJAS_KEY')

# Add these environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Initialize Google Cloud Vision client
if os.getenv('GOOGLE_CREDENTIALS'):
    # Create credentials file from environment variable
    credentials_dict = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
    with open('google_credentials.json', 'w') as f:
        json.dump(credentials_dict, f)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_credentials.json'

client = vision.ImageAnnotatorClient()

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

COMMON_SERVING_SIZES = {
    "apple": 182,  # medium apple
    "banana": 118,  # medium banana
    "rice": 158,   # 1 cup cooked
    "pizza": 107,  # 1 slice
    "chicken breast": 172,  # 1 medium breast
    "sandwich": 230,  # 1 regular sandwich
    "burger": 240,  # 1 regular burger
    "pasta": 140,   # 1 cup cooked
}

def get_nutrition_data(food_name):
    """Get nutritional information from API Ninjas with estimated serving size"""
    api_url = 'https://api.api-ninjas.com/v1/nutrition?query={}'.format(food_name)
    headers = {
        'X-Api-Key': API_NINJAS_KEY
    }
    
    try:
        response = requests.get(api_url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.ok:
            foods = response.json()
            if foods:
                food = foods[0]
                
                # Get serving size or default to 100g
                serving_size = COMMON_SERVING_SIZES.get(food_name.lower(), 100)
                multiplier = serving_size / 100  # Convert from per 100g to serving size
                
                return {
                    "food": food_name,
                    "serving_size": serving_size,
                    "fat": round(food.get('fat_total_g', 0) * multiplier, 1),
                    "carbs": round(food.get('carbohydrates_total_g', 0) * multiplier, 1),
                    "fiber": round(food.get('fiber_g', 0) * multiplier, 1),
                    "sugar": round(food.get('sugar_g', 0) * multiplier, 1),
                    "sodium": round(food.get('sodium_mg', 0) * multiplier),
                    "potassium": round(food.get('potassium_mg', 0) * multiplier),
                    "cholesterol": round(food.get('cholesterol_mg', 0) * multiplier)
                }
    except Exception as e:
        print(f"Error getting nutrition data: {str(e)}")
    return None

def process_image(photo_url):
    """Sends the image to Google Vision API and extracts food-related labels."""
    try:
        print(f"Attempting to download image from: {photo_url}")
        response = requests.get(photo_url)
        image_content = response.content
        print(f"Image downloaded successfully, size: {len(image_content)} bytes")

        image = vision.Image(content=image_content)
        print("Created Vision API Image object")

        response = client.label_detection(image=image)
        labels = response.label_annotations
        
        # Print all labels with their scores
        print("\nAll detected labels:")
        for label in labels:
            print(f"- {label.description} (confidence: {label.score})")

        # Extract food-related labels with lower confidence threshold
        food_items = [label.description for label in labels if label.score > 0.5]  # Lowered threshold from 0.6 to 0.5
        print(f"\nFiltered food items: {food_items}")

        # Try to get nutrition data for each detected item until we find one
        if food_items:
            for food_item in food_items:
                print(f"\nTrying to get nutrition data for: {food_item}")
                nutrition_data = get_nutrition_data(food_item)
                if nutrition_data:
                    print(f"Found nutrition data for {food_item}")
                    return nutrition_data
                else:
                    print(f"No nutrition data found for {food_item}")
        else:
            print("No food items detected with confidence > 0.5")
        return None

    except Exception as e:
        print(f"Error in process_image: {str(e)}")
        return None

async def handle_photo(update: Update, context: CallbackContext):
    try:
        user = update.message.from_user
        user_id = update.message.chat_id
        
        # Create a full name by combining first and last name (if available)
        full_name = user.first_name
        if user.last_name:
            full_name += f" {user.last_name}"
        
        photo = update.message.photo[-1].file_id
        print(f"Received photo with file_id: {photo}")
        
        file = await context.bot.get_file(photo)
        photo_url = file.file_path
        print(f"Got photo URL: {photo_url}")
        
        food_data = process_image(photo_url)
        print(f"Processed food data: {food_data}")
        
        if food_data:
            # Store successful identification in Supabase
            data = {
                'user_id': str(user_id),
                'user_name': full_name,  # Combined first and last name
                'username': user.username,  # @handle
                'timestamp': datetime.utcnow().isoformat(),
                'food_identified': food_data['food'],
                'serving_size': food_data['serving_size'],
                'fat': food_data['fat'],
                'carbs': food_data['carbs'],
                'fiber': food_data['fiber'],
                'sugar': food_data['sugar'],
                'sodium': food_data['sodium'],
                'potassium': food_data['potassium'],
                'cholesterol': food_data['cholesterol'],
                'success': True
            }
            
            supabase.table('food_logs').insert(data).execute()
            
            message = (
                f"🍽 Identified Food: {food_data['food'].title()}\n"
                f"\n📊 Nutritional Information:\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Fat: {food_data['fat']}g\n"
                f"• Carbohydrates: {food_data['carbs']}g\n"
                f"     ├ Fiber: {food_data['fiber']}g\n"
                f"     └ Sugar: {food_data['sugar']}g\n"
                f"\n🧂 Minerals:\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Sodium: {food_data['sodium']}mg\n"
                f"• Potassium: {food_data['potassium']}mg\n"
                f"• Cholesterol: {food_data['cholesterol']}mg"
            )
            await update.message.reply_text(message)
        else:
            # Log failed attempts in Supabase
            data = {
                'user_id': str(user_id),
                'user_name': full_name,  # Combined first and last name
                'username': user.username,  # @handle
                'timestamp': datetime.utcnow().isoformat(),
                'success': False
            }
            
            supabase.table('food_logs').insert(data).execute()
            
            await update.message.reply_text(
                "Sorry, I couldn't identify the food item or get its nutritional information. "
                "Please make sure the image is clear and shows a single food item."
            )
            
    except Exception as e:
        print(f"Error in handle_photo: {str(e)}")
        await update.message.reply_text(
            "Sorry, there was an error processing your image. "
            "Please try again with a different photo."
        )

async def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the Food Nutrition Bot!\n\n"
        "Send me a photo of any food item, and I'll tell you its nutritional information.\n\n"
        "Available commands:\n"
        "/history - See your recent food logs\n"
        "/stats - View your usage statistics\n\n"
        "Just send a clear photo of a single food item, and I'll do my best to identify it "
        "and provide you with detailed nutritional facts."
    )
    await update.message.reply_text(welcome_message)

async def my_history(update: Update, context: CallbackContext):
    """Show user their food logging history"""
    try:
        user_id = str(update.message.chat_id)
        
        # Get last 5 successful food logs for this user
        response = supabase.table('food_logs')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('success', True)\
            .order('timestamp', desc=True)\
            .limit(5)\
            .execute()
        
        if response.data:
            message = "🗓 Your Recent Food History:\n\n"
            for log in response.data:
                food = log['food_identified']
                date = datetime.fromisoformat(log['timestamp']).strftime('%Y-%m-%d %H:%M')
                message += f"• {food} (logged on {date})\n"
        else:
            message = "You haven't logged any foods yet!"
            
        await update.message.reply_text(message)
        
    except Exception as e:
        print(f"Error in my_history: {str(e)}")
        await update.message.reply_text("Sorry, couldn't fetch your history right now.")

async def my_stats(update: Update, context: CallbackContext):
    """Show user their statistics"""
    try:
        user_id = str(update.message.chat_id)
        
        # Get total logs and success rate
        response = supabase.table('food_logs')\
            .select('success')\
            .eq('user_id', user_id)\
            .execute()
        
        if response.data:
            total_logs = len(response.data)
            successful_logs = sum(1 for log in response.data if log['success'])
            success_rate = (successful_logs / total_logs) * 100
            
            message = (
                f"📊 Your Stats:\n\n"
                f"Total photos sent: {total_logs}\n"
                f"Successfully identified: {successful_logs}\n"
                f"Success rate: {success_rate:.1f}%"
            )
        else:
            message = "You haven't used the bot yet! Send me a food photo to get started."
            
        await update.message.reply_text(message)
        
    except Exception as e:
        print(f"Error in my_stats: {str(e)}")
        await update.message.reply_text("Sorry, couldn't fetch your stats right now.")

def main():
    """Start the bot."""
    try:
        print("Starting bot application...")
        application = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        print("Adding command handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(CommandHandler("history", my_history))
        application.add_handler(CommandHandler("stats", my_stats))
        
        # Add error handler
        print("Adding error handler...")
        application.add_error_handler(error_handler)

        PORT = int(os.getenv('PORT', '10000'))
        APP_URL = os.getenv('APP_URL')
        
        print(f"Configuration - Port: {PORT}, URL: {APP_URL}")

        if APP_URL:
            print(f"Starting webhook on {APP_URL}/webhook")
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=f"{APP_URL}/webhook",
                webhook_path="/webhook",
                secret_token=os.getenv('WEBHOOK_SECRET', 'your-secret-token'),
                drop_pending_updates=True
            )
        else:
            print("Starting polling mode...")
            application.run_polling()
            
    except Exception as e:
        print(f"Error starting bot: {str(e)}")
        raise

if __name__ == '__main__':
    print("Bot script starting...")
    main()