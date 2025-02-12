from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
import json
import re
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from typing import Dict, List, Optional, Tuple
import requests  # For news API
# import tweepy  # For Twitter (requires authentication setup) - commented out for now

load_dotenv()

# --- Helper Functions ---

def calculate_moving_average(prices: List[float], window: int) -> Optional[float]:
    """Calculates a simple moving average."""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

def calculate_rsi(prices: List[float], window: int = 14) -> Optional[float]:
    """Calculates the Relative Strength Index (RSI)."""
    if len(prices) < window + 1:
        return None

    deltas = [prices[i] - prices[i - 1] for i in range(len(prices) - window, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window

    if avg_loss == 0:
        return 100  # Avoid division by zero

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

async def get_news_sentiment(token_name: str) -> Optional[float]:
    """Fetches news articles about the token and analyzes sentiment (Conceptual)."""
    # Replace with your actual News API key and endpoint
    news_api_key = "YOUR_NEWS_API_KEY"  
    news_url = f"https://newsapi.org/v2/everything?q={token_name}&apiKey={news_api_key}"

    try:
        response = requests.get(news_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        # --- Sentiment Analysis (Conceptual - Requires a sentiment analysis library) ---
        # This is a placeholder.  You'd use a library like TextBlob, VADER, or a
        # dedicated sentiment analysis API.
        total_sentiment = 0
        article_count = 0
        if data['articles']: #check if articles exist
            for article in data['articles']:
                # Example using a hypothetical sentiment analysis function:
                # article_sentiment = analyze_sentiment(article['title'] + " " + article['description'])
                # total_sentiment += article_sentiment
                # article_count += 1
                pass #remove pass and uncomment above lines once sentiment analysis is implemented

            if article_count > 0:
                average_sentiment = total_sentiment / article_count
                return average_sentiment
        # ---
        return None  # No articles or sentiment analysis failed

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return None

# --- (Optional) Twitter Sentiment - Requires Tweepy and API Keys ---
# async def get_twitter_sentiment(token_name: str) -> Optional[float]:
#    """Fetches tweets about the token and analyzes sentiment (Conceptual)."""
#     # Replace with your actual Twitter API keys
#     consumer_key = "YOUR_CONSUMER_KEY"
#     consumer_secret = "YOUR_CONSUMER_SECRET"
#     access_token = "YOUR_ACCESS_TOKEN"
#     access_token_secret = "YOUR_ACCESS_TOKEN_SECRET"

#     auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
#     auth.set_access_token(access_token, access_token_secret)
#     api = tweepy.API(auth)

#     try:
#         tweets = api.search_tweets(q=token_name, lang="en", count=100)  # Adjust count as needed

#         # --- Sentiment Analysis (Conceptual) ---
#         total_sentiment = 0
#         for tweet in tweets:
#             # Example:
#             # tweet_sentiment = analyze_sentiment(tweet.text)
#             # total_sentiment += tweet_sentiment
#             pass #remove and uncomment above after implementing sentiment analysis
#         if tweets:
#             average_sentiment = total_sentiment / len(tweets)
#             return average_sentiment
#         # ---
#         return None

#     except tweepy.TweepyException as e:
#         print(f"Error fetching tweets: {e}")
#         return None
# ---

async def extract_token_data(agent: Agent, token_link_text: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Extracts data for a single token, including external data."""
    try:
        # Navigate to the token page
        click_result = await agent.click_element(selector=f"text={token_link_text}", selector_type="text")
        if not click_result:
             return None, f"Failed to click token link: {token_link_text}"

        await asyncio.sleep(2)

        # Dynamic Content Handling
        try:
            await agent.wait_for_selector(selector="div.price-change", timeout=10000)
        except PlaywrightTimeoutError:
            return None, "Timeout: Price data did not load."

        # Extract data using CSS selectors
        extracted_data_result = await agent.extract_content(
            goal="get token name, price changes (1H, 2H, 4H, 8H, 24H), 24-hour volume, and sentiment.",
            selector="div.main-container"
        )

        if not (extracted_data_result and extracted_data_result.content):
            return None, "Failed to extract content."

        extracted_data = extracted_data_result.content
        token_data = {'price_changes': {}}

        # --- Data Parsing ---
        try:
            # Token Name
            token_data['name'] = list(extracted_data.keys())[0].split('|')[0].strip()

            price_changes = {}

            #find price changes in nested dict
            for key, value in extracted_data.items():
                if isinstance(value,dict) and "1H" in value: #find the dict that contains price change info.
                    price_changes = value
                    break;

            # Extract and convert price changes
            for period in ['1H', '2H', '4H', '8H', '24H']:
                change_str = price_changes.get(period)
                if change_str:
                    # Remove + and % signs, and convert to float
                    change_str = change_str.replace("+", "").replace("%", "").strip()
                    try:
                        token_data['price_changes'][period] = float(change_str)
                    except ValueError:
                        token_data['price_changes'][period] = None
                else:
                    token_data['price_changes'][period] = None


            volume_str = None
            #find volume in nested dict
            for key, value in extracted_data.items():
                if isinstance(value,dict):
                    for k,v in value.items():
                        if "24h" in k: #find dict entries that have 24h, indicating volume.
                            volume_str = v;
                            break;
                    if volume_str:
                        break;

            if volume_str:
                # Extract numerical value from volume string (e.g., "$92.04M")
                match = re.search(r"(\d+\.?\d*)([MK]?)", volume_str)  # Regex to handle M and K
                if match:
                    value, suffix = match.groups()
                    value = float(value)
                    if suffix == 'M':
                        value *= 1000000
                    elif suffix == 'K':
                        value *= 1000
                    token_data['volume_24h'] = value
                else:
                    token_data['volume_24h'] = None
            else:
                token_data['volume_24h'] = None


            # Extract sentiment (if available - it's often 0%/0% on Birdeye)
            sentiment_positive = "0%"  # Default values
            sentiment_negative = "0%"

            for key, value in extracted_data.items():
                if isinstance(value,dict) and "positive" in value:
                    sentiment = value
                    sentiment_positive = sentiment.get('positive', '0.00%')
                    sentiment_negative = sentiment.get('negative', '0.00%')
                    break

            token_data['sentiment'] = {
                'positive': float(sentiment_positive.replace("%", "")),
                'negative': float(sentiment_negative.replace("%", "")),
            }

        except (KeyError, ValueError, TypeError) as e:
            return None, f"Error parsing extracted data: {e}"
        # --- End Data Parsing ---

        # --- External Data Integration ---
        token_name = token_data.get('name', '')
        if token_name:
            news_sentiment = await get_news_sentiment(token_name)  # Fetch news sentiment
            if news_sentiment is not None:
                token_data['news_sentiment'] = news_sentiment

            # twitter_sentiment = await get_twitter_sentiment(token_name)  # Fetch Twitter sentiment
            # if twitter_sentiment is not None:
            #     token_data['twitter_sentiment'] = twitter_sentiment
        # ---

        return token_data, None

    except PlaywrightTimeoutError:
        return None, "Timeout error while loading token page."
    except Exception as e:
        return None, str(e)


async def generate_recommendations(token_data_list: List[Dict], llm: ChatOpenAI) -> str:
    """Generates trading recommendations using the LLM."""
    if not token_data_list:
        return "No data available for recommendations."

    prompt = "Given the following cryptocurrency token data, provide concise trading recommendations (Buy, Sell, Hold, or more detailed advice) for each token. Consider price changes, volume, sentiment, and external data (news sentiment):\n\n"

    for data in token_data_list:
        prompt += f"Token: {data.get('name', 'N/A')}\n"
        prompt += "  Price Changes:\n"
        for period, change in data.get('price_changes', {}).items():
            prompt += f"    {period}: {change if change is not None else 'N/A'}%\n"
        prompt += f"  24H Volume: {data.get('volume_24h', 'N/A')}\n"
        prompt += f"  Sentiment: Positive: {data.get('sentiment', {}).get('positive', 'N/A')}%, Negative: {data.get('sentiment', {}).get('negative', 'N/A')}%\n"
        prompt += f"  News Sentiment: {data.get('news_sentiment', 'N/A')}\n"  # Include news sentiment
        # prompt += f"  Twitter Sentiment: {data.get('twitter_sentiment', 'N/A')}\n" # Include Twitter sentiment
        prompt += "\n"

    prompt += "Provide a brief overall market analysis if trends are apparent across multiple tokens."

    # Use the LLM to generate recommendations
    try:
        response = await llm.ainvoke(prompt)
        return response.content

    except Exception as e:
        return f"Error generating recommendations: {e}"


async def main():
    agent = Agent(
        task="""
        Analyze the top 3 trending tokens on Birdeye.so.  For each token:
        1. Navigate to the token's page.
        2. Extract: token name, price changes (1H, 2H, 4H, 8H, 24H), 24-hour volume, sentiment.
        3.  Integrate external data: news sentiment.
        4. Attempt to find comments (but don't get stuck).
        5. Navigate available tabs (Traders, Markets, Technicals - if present)
        Synthesize data into a report and generate trading recommendations.
        """,
        llm=ChatOpenAI(model="gpt-4o")
    )

    # --- Initial Navigation ---
    search_result = await agent.search(query="Birdeye.so")
    if not search_result:
        print("Failed to search for Birdeye.so")
        return

    click_result = await agent.click_element(selector='a[href="https://birdeye.so/"]', selector_type="css")
    if not click_result:
        print("Could not find Birdeye link on google")
        return
    await asyncio.sleep(3)

    # --- Get Top Trending Tokens ---
    try:
        trending_tokens_result = await agent.extract_content(
            goal="Get the names of the top 3 trending tokens.",
            selector="div.trending-tokens-container"
        )
        if trending_tokens_result and trending_tokens_result.content:
            trending_tokens_names = list(trending_tokens_result.content.keys())[:3]
        else:
            print("Failed to extract trending token names.")
            return

    except Exception as e:
        print(f"Error getting trending tokens: {e}")
        return

    # --- Process Tokens Asynchronously ---
    token_data_list = []
    tasks = [extract_token_data(agent, token_name) for token_name in trending_tokens_names]
    results = await asyncio.gather(*tasks)

    for token_data, error in results:
        if token_data:
            token_data_list.append(token_data)
        elif error:
            print(f"Error processing token: {error}")

    # --- Generate Recommendations ---
    recommendations = await generate_recommendations(token_data_list, agent.llm)

    # --- Report and Recommendations ---
    if token_data_list:
        report = "Trading Report:\n\n"
        for data in token_data_list:
            report += f"Token: {data.get('name', 'N/A')}\n"
            report += "  Price Changes:\n"
            for period, change in data.get('price_changes', {}).items():
                report += f"    {period}: {change if change is not None else 'N/A'}%\n"
            report += f"  24H Volume: {data.get('volume_24h', 'N/A')}\n"
            report += f"  Sentiment: Positive: {data.get('sentiment', {}).get('positive', 'N/A')}%, Negative: {data.get('sentiment', {}).get('negative', 'N/A')}%\n"
            report += f"  News Sentiment: {data.get('news_sentiment', 'N/A')}\n"  # Include news sentiment
            # report += f"  Twitter Sentiment: {data.get('twitter_sentiment', 'N/A')}\n" # Include Twitter Sentiment
            report += "\n"

        report += "Recommendations:\n" + recommendations

        print(report)
        await agent.done(text=report)

    else:
        print("No token data collected.")
        await agent.done(text="Failed to collect data for any trending tokens.")


if __name__ == "__main__":
    asyncio.run(main())