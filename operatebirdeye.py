from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
import json
import re  # For regular expressions
from playwright.async_api import TimeoutError as PlaywrightTimeoutError  # Import Playwright's TimeoutError
from typing import Dict, List, Optional, Tuple

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

async def extract_token_data(agent: Agent, token_link_text: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Extracts data for a single token."""
    try:
        # Navigate to the token page using text-based selection (more robust)

        # This is a conceptual implementation of how you might click
        # a link based on its text content using `browser_use`.  You may need
        # to adapt the specific method based on `browser_use`'s API.
        
        click_result = await agent.click_element(selector=f"text={token_link_text}", selector_type="text") #use text content
        if not click_result:
             return None, f"Failed to click token link: {token_link_text}"

        await asyncio.sleep(2)  # Short wait for page load

        # --- Dynamic Content Handling (Conceptual) ---
        # Example of waiting for an element (replace with actual selector)
        # try:
        #     await agent.page.wait_for_selector("div.comments-section", timeout=5000)  # Wait 5 seconds
        # except PlaywrightTimeoutError:
        #     print("Comments section did not load within timeout.")
        # ---

        # Extract data using robust selectors (CSS or XPath)
        # Example:  (You'll need to inspect Birdeye.so to get the correct selectors)
        
        extracted_data_result = await agent.extract_content(goal="get token name, price changes (1H, 2H, 4H, 8H, 24H), 24-hour volume, and sentiment.",
                                        selector="#__next > main > div:nth-of-type(2) > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div:nth-of-type(1) > div > div:nth-of-type(1) > div:nth-of-type(1) > div")

        if extracted_data_result and extracted_data_result.content:
            extracted_data = extracted_data_result.content
        else:
            return None, "Failed to extract content."
        

        # --- Data Parsing (Example - Adapt to actual structure) ---
        token_data = {}
        try:
            # The below is an example of how the extracted data could be.  It will almost
            # certainly be different.  Adapt this parsing logic to match the actual
            # structure of the `extracted_data` dictionary.
            print(extracted_data) #always print the extracted data to make it easier to process
            token_data['name'] = list(extracted_data.keys())[0] # gets the token name assuming it is the first key of the dict
            data = extracted_data.get(token_data['name'],{}) #gets nested dict of token information
            
            price_changes = data.get('Price',{}) #gets 'Price' dict

            token_data['price_changes'] = {
                '1H': float(price_changes.get('1H', '0%').replace("%","")),
                '2H': float(price_changes.get('2H', '0%').replace("%","")),
                '4H': float(price_changes.get('4H', '0%').replace("%","")),
                '8H': float(price_changes.get('8H', '0%').replace("%","")),
                '24H': float(price_changes.get('24H', '0%').replace("%","")),
            }
           
            volume_data = data.get('Volume',{}) #get 'Volume' dict

            token_data['volume_24h'] = volume_data.get('24h TRUMP-USDC', "0")  # Adjust key as needed
            
            sentiment_data = data.get('Sentiment',{})
            token_data['sentiment'] = {
                'positive': sentiment_data.get('positive', '0.00%'),
                'negative': sentiment_data.get('negative', '0.00%')
                }

        except (KeyError, ValueError, TypeError) as e:
            return None, f"Error parsing extracted data: {e}"
        # --- End Data Parsing ---
        
        # --- Technical Indicator Calculation (Conceptual)---
        #  You'd need historical price data for this, which might require
        #  additional scraping or API calls.
        # token_data['moving_average_20'] = calculate_moving_average(historical_prices, 20)
        # token_data['rsi'] = calculate_rsi(historical_prices)
        # ---

        return token_data, None

    except PlaywrightTimeoutError:
        return None, "Timeout error while loading token page."
    except Exception as e:
        return None, str(e)


async def main():
    agent = Agent(
        task="""
        Analyze the top 3 trending tokens on Birdeye.so.  For each token:
        1. Navigate to the token's page.
        2. Extract: token name, price changes (1H, 2H, 4H, 8H, 24H), 24-hour volume, sentiment.
        3. Attempt to find comments (but don't get stuck).
        4. Navigate available tabs (Traders, Markets, Technicals)
        Synthesize data into a report with trading recommendations based on extracted metrics.
        """,
        llm=ChatOpenAI(model="gpt-4o"),
        max_iterations=60,  # Increased for more complex task
        verbose=True,
    )
    
    # --- Initial Navigation ---
    # we navigate to the webpage using google first, so it will store the browsing context
    search_result = await agent.search_google(query="Birdeye.so")
    if not search_result:
        print("Failed to search for Birdeye.so")
        return
    
    # Find the link to Birdeye.so (using a more robust method than index)
    #This selects using href, which is a lot more reliable than index
    click_result = await agent.click_element(selector='a[href="https://birdeye.so/"]', selector_type="css")
    if not click_result:
        print("Could not find Birdeye link on google")
        return
    await asyncio.sleep(3) #wait for page to load

    # --- Get Top Trending Tokens (Conceptual - Adapt Selectors) ---
    # Extract the *names* or *text links* of the top 3 trending tokens.
    # This is a *critical* step and needs to be done robustly.
    # You'll need to inspect the Birdeye.so HTML to find the right selectors.
    try:
      
      #extract token names
      trending_tokens_result = await agent.extract_content(
            goal="Get the names of the top 3 trending tokens.",
            selector="#__next > main > div:nth-of-type(2) > section > div:nth-of-type(2) > div > div > div > div:nth-of-type(1) > table > tbody" #targets the table
      )
      if trending_tokens_result and trending_tokens_result.content:
            trending_tokens_names = list(trending_tokens_result.content.keys())[:3] #gets the top 3 token names
      else:
            print("Failed to extract trending token names")
            return

    except Exception as e:
        print(f"Error getting trending tokens: {e}")
        return

    # --- Process Tokens Asynchronously ---
    token_data_list = []
    tasks = [extract_token_data(agent, token_name) for token_name in trending_tokens_names]
    results = await asyncio.gather(*tasks)  # Run all token extractions concurrently

    for token_data, error in results:
        if token_data:
            token_data_list.append(token_data)
        elif error:
            print(f"Error processing token: {error}")


    # --- Synthesize Report (Conceptual) ---
    # Use the collected `token_data_list` to generate a report.
    # This is where you would use the LLM to generate recommendations.
    if token_data_list:
        report = "Trading Report:\n\n"
        for data in token_data_list:
            report += f"Token: {data.get('name', 'N/A')}\n"
            report += f"  24H Price Change: {data.get('price_changes', {}).get('24H', 'N/A')}%\n"
            report += f"  24H Volume: {data.get('volume_24h', 'N/A')}\n"
            report += f"  Sentiment: Positive: {data.get('sentiment',{}).get('positive','N/A')}, Negative: {data.get('sentiment',{}).get('negative','N/A')}\n"
           # report += f"  Moving Average (20): {data.get('moving_average_20', 'N/A')}\n" #if implemented
           # report += f"  RSI: {data.get('rsi', 'N/A')}\n" #if implemented
            report += "\n"

        # --- LLM-Based Recommendations (Conceptual) ---
        # You would use the LLM here to generate more sophisticated
        # recommendations based on the extracted data.
        # Example (using a hypothetical `generate_recommendations` function):
        # recommendations = await generate_recommendations(token_data_list)
        # report += f"Recommendations:\n{recommendations}\n"
        # ---
        print (report)
        await agent.done(text=report)

    else:
        print("No token data collected.")
        await agent.done(text="Failed to collect data for any trending tokens.")
    # ---


if __name__ == "__main__":
    asyncio.run(main())