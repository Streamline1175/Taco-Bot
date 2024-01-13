import discord
from discord.ext import commands
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta
import requests
import time
import pytz
from geopy.geocoders import Nominatim
from geopy.timezone import Timezone
from tzwhere import tzwhere
from timezonefinder import TimezoneFinder

# Create an instance of discord.Intents
intents = discord.Intents.default()
intents.message_content = True  # To listen to message content

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}\n')

@bot.command()
async def tacorecipe(ctx):
    print("hello")

def shorten_url(original_url):
    create_short_url = "" # Tiny URL API Key
    try:
        tiny_url = f"https://api.tinyurl.com/create?api_token={create_short_url}"
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }

        data = {
            'url': original_url,
        }

        response = requests.post(tiny_url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            shortened_url = result.get('data', {}).get('tiny_url', '')
            return shortened_url
        else:
            print(f"Failed to shorten URL. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error while shortening URL: {e}")
        return None

def get_timezone_for_location(latitude, longitude):
    geolocator = Nominatim(user_agent="taco_bot")
    location = geolocator.reverse((latitude, longitude), language='en')  # Reverse geocoding to get location details

    timezone_finder = TimezoneFinder()
    timezone_str = timezone_finder.timezone_at(lng=longitude, lat=latitude)
    timezone_val = pytz.timezone(timezone_str)
    
    # Calculate the offset from CST (America/Chicago)
    cst_timezone = pytz.timezone('America/Chicago')
    current_time = datetime.now()
    location_time = datetime.now(timezone_val)
    cst_offset = (timezone_val.utcoffset(current_time) - cst_timezone.utcoffset(current_time)).total_seconds() / 3600
    
    return timezone_val, cst_offset
    
def get_timezone_offset_from_cst(target_timezone):
    cst_timezone = pytz.timezone('America/Chicago')

    # Create a naive datetime object (without timezone) in UTC
    current_time_naive = datetime.utcnow()

    # Localize the naive datetime object to CST
    current_time_cst = cst_timezone.localize(current_time_naive, is_dst=None)

    # Convert the localized datetime object to the target timezone
    target_timezone = pytz.timezone(target_timezone)
    current_time_target = current_time_cst.astimezone(target_timezone)

    # Get the offset between CST and the target timezone
    offset = target_timezone.utcoffset(current_time_target).total_seconds() / 3600

    return offset

@bot.command()
async def tacos(ctx, location: str):
    requestor = ctx.author.mention
    api_key = '' # Yelp Developer API Key
    base_url = "https://api.yelp.com/v3/businesses/search?"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    params = {
        "term": "tacos",
        "location": f"{location}",
        "categories": "tacos",
        "sort_by": "rating",
        "radius": 40000,
        "limit": 50  # You can adjust the limit as needed
    }
    
    response = requests.get(base_url, headers=headers, params=params)
    
    # Extract rate limit information from the headers
    rate_limit_remaining = response.headers.get('RateLimit-Remaining')
    rate_limit_reset_time = response.headers.get('RateLimit-ResetTime')
    
    # american_timezones = ['America/New_York', 'America/Los_Angeles', 'America/Denver', 'America/Phoenix']

    # timezone_offsets = {tz: get_timezone_offset_from_cst(tz) for tz in american_timezones}

    # Print the remaining API calls
    print(f"Remaining API Calls: {rate_limit_remaining}")
    print(f"API Calls Reset: {rate_limit_reset_time}")
        
    if response.status_code == 200:
        data = response.json()
        returned_places = 10
        
        embed = DiscordEmbed(title=f"Top {returned_places} Taco Places - {location}", color=0xFF5733)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        embed.set_description(description="All of these Taco Places are within a 25 mile radius at the center of the location that you passed to the bot.")
        embed.set_footer(text=f"Made by Fire, the Lit Mage • Timestamp: {current_time}")
        
        # Filter businesses with a rating below 4
        filtered_businesses = [business for business in data.get("businesses", []) if business.get("rating", 0) >= 4]
        
        # Sort businesses based on review count and rating
        sorted_businesses = sorted(filtered_businesses, key=lambda x: (x.get("review_count"), x.get("rating")), reverse=True)
        
        # Get the top 10 businesses based on rating
        top_businesses = sorted_businesses[:returned_places]

        # Initialize lists to store information for each header
        business_info = []
        for business in top_businesses:
            business_id = business.get("id")
            name = business.get("name")
            rating = business.get("rating")
            review_count = business.get("review_count")
            price = "-" if business.get("price") is None else business.get("price", "-")
            long_url = business.get("url")
            yelp_url = shorten_url(long_url)
            address = business.get("display_address")
            meter_distance = business.get("distance")
            miles_distance = int(round(meter_distance / 1609.34, 0))
            foodtrucks_exist = any(category.get("alias") == "foodtrucks" for category in business.get("categories", []))
            food_truck_emoji = "🚚" if foodtrucks_exist else ""
            #availability = "Open" if not business.get("is_closed") else "Closed"
            
            # Make a request to the business details API with retry mechanism
            retry_count = 0
            max_retries = 3
            while retry_count < max_retries:
                business_url = f"https://api.yelp.com/v3/businesses/{business_id}"
                business_response = requests.get(business_url, headers=headers)

                if business_response.status_code == 200:
                    business_details = business_response.json()
                    # Now you can use the details from business_details
                    is_open_now = business_details.get("hours", [{}])[0].get("is_open_now", False)
                    
                    if is_open_now == True:
                        # Calculate remaining open time
                        remaining_open_time = ""
                        current_day = datetime.now().weekday()
                        #print(current_day)
                        # Define the local time zone for Texas (Central Time)
                        # Extract latitude and longitude from coordinates
                        coordinates = business_details.get("coordinates", {})
                        latitude = coordinates.get("latitude", 0)
                        longitude = coordinates.get("longitude", 0)
                        location_timezone, cst_offset = get_timezone_for_location(latitude, longitude)
                        #print(location_timezone)

                        for hours_entry in business_details.get("hours", []):
                            for open_entry in hours_entry.get("open", []):
                                if open_entry["day"] == current_day:
                                    end_time = datetime.strptime(open_entry["end"], "%H%M")
                                    current_time = datetime.now().time()
                                    remaining_time = end_time - datetime.combine(datetime.now().date(), current_time) - timedelta(hours=cst_offset)
                                    
                                    # end_time = datetime.strptime(open_entry["end"], "%H%M")
    
                                    # # Convert end_time to the local timezone
                                    # end_time_local = location_timezone.localize(end_time)
                                    
                                    # # Calculate remaining time in local timezone
                                    # remaining_time = end_time_local - datetime.now(location_timezone)
                                    
                                    # # Ensure remaining time is not negative
                                    # remaining_time = max(remaining_time, timedelta(seconds=0))
                                    
                                    # Format remaining time
                                    remaining_hours, remainder = divmod(remaining_time.seconds, 3600)
                                    remaining_minutes = remainder // 60
                                    remaining_open_time = f"{remaining_hours}h {remaining_minutes}m"
                                    #remaining_open_time = f"{int(remaining_time // 3600)}h {int((remaining_time % 3600) // 60)}m"
                    else:
                        remaining_open_time = ""                     
                    break  # Break the loop if successful
                elif business_response.status_code == 429:
                    # If rate limit exceeded, wait for a while and retry
                    print("Rate limit hit")
                    retry_count += 1
                    time.sleep(5)  # Wait for 5 seconds before retrying
                else:
                    print(f"Error fetching business details: {business_response.status_code}")
                    is_open_now = False
                    break  # Break the loop for other errors

            # If still unsuccessful after retries, set default value
            else:
                print(f"Failed to fetch business details after {max_retries} retries")
                is_open_now = False

            # Append emoji based on availability or absence of hours information
            status_emoji = "🟢" if is_open_now else ("🔴" if is_open_now is not None else "🟡")

            business_info.append({
                "name": f"{status_emoji}{food_truck_emoji} [{name}]({yelp_url})",
                "rating_reviews_price_distance_closes_in": f"{rating} • {review_count} • {'-' if price is None else price} • {miles_distance} mi{' • ' + remaining_open_time if remaining_open_time else ''}",
            })
            
            #print(business_info)

        # Ensure that the lists are not empty before joining
        business_names_str = "\n".join([info["name"] for info in business_info]) if business_info else "N/A"
        ratings_reviews_prices_distance_closes_in_str = "\n".join([info["rating_reviews_price_distance_closes_in"] for info in business_info]) if business_info else "N/A"
        #closes_in_str = "\n".join([info["closes_in"] for info in business_info]) if business_info else "N/A"

        # Add headers with joined values
        embed.add_embed_field(name="Business Name", value=business_names_str, inline=True)
        embed.add_embed_field(name="⭐ • 📝 • 💳 • 🚗 • 🔴", value=ratings_reviews_prices_distance_closes_in_str, inline=True)
        #embed.add_embed_field(name="Closes In", value=closes_in_str, inline=True)
        #embed.add_embed_field(name="Requestor", value=ctx.author.mention)
        
        # Get the channel where the command was invoked
        channel = ctx.channel

        # Check if the channel is a TextChannel (ignore other channel types like DMs)
        if isinstance(channel, discord.TextChannel):
            # Check if a webhook with the name "Taco Bot Webhook" already exists
            existing_webhooks = await channel.webhooks()
            existing_taco_webhook = next((webhook for webhook in existing_webhooks if webhook.name == "Taco Bot Webhook"), None)

            if existing_taco_webhook:
                # If the webhook already exists, use it
                webhook_url = existing_taco_webhook.url
            else:
                # If the webhook doesn't exist, create a new one
                webhook = await channel.create_webhook(name="Taco Bot Webhook")
                webhook_url = webhook.url
        else:
            # Handle cases where the command is not invoked in a TextChannel
            await ctx.send("This command can only be used in text channels.")
            return

        # Add character count for the entire webhook to the total count
        #total_characters = len(str(embed))

        # Print the total character count
        #print(f"Total characters: {total_characters}")

        # Send the message with user mention in the content
        webhook_content = f"{ctx.author.mention}"

        # Send the embed to the channel
        webhook = DiscordWebhook(url=webhook_url, content=webhook_content, embeds=[embed], username="Taco Bot")
        response = webhook.execute()
                
    else:
        if response.status_code == 429:
            # Rate limit exceeded, print a message and provide the remaining time until reset
            reset_time = datetime.datetime.strptime(rate_limit_reset_time, "%Y-%m-%dT%H:%M:%S%z")
            current_time_utc = datetime.datetime.utcnow()
            time_until_reset = reset_time - current_time_utc
            print(f"Daily API limit exceeded. Resets at {reset_time.isoformat()} UTC. Remaining time: {time_until_reset}")
            await ctx.send(f"[{requestor}] Daily API limit exceeded. Resets at {reset_time.isoformat()} UTC. Remaining time: {time_until_reset}")
        else:
            try:
                error_message = response.json().get("error", {}).get("description", "Unknown error")
                print(f"Error ({response.status_code}): {error_message}")

                # Log the entire response content for further inspection
                print(f"Full Response Content: {response.text}")

            except Exception as e:
                print(f"Error ({response.status_code}): Unable to parse error message")

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot.run('') # Discord Bot Token
