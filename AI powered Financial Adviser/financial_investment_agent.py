import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langchain.tools import tool
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import uuid
from tabulate import tabulate

# unable to fetch exchange rate data.. look for this function & fix it.
def render_table(text: str) -> str:
    """
    Detect markdown-style portfolio tables and render them as pretty console tables.
    If no table is found, return original text.
    """
    rows = []
    capture = False
    for line in text.splitlines():
        if line.strip().startswith("| Asset Class"):
            capture = True
            continue
        if capture and line.strip().startswith("|---"):
            continue
        if capture and line.strip().startswith("|") and not line.strip().startswith("|---"):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) == 4:
                rows.append(parts)
        else:
            # stop capturing if table ends
            if capture and not line.strip().startswith("|"):
                break
    if rows:
        return tabulate(rows, headers=["Asset Class", "Allocation (%)", "Dollar Amount", "Rationale"], tablefmt="pretty")
    return text

# Set up APIs
gemini_api_key = "YOUR_GOOGLE_API_KEY_HERE"  # Replace with your actual Google API key
exchange_rate_api_key = "YOUR_EXCHANGE_RATE_API_KEY_HERE"  # Replace with your actual Exchange Rate API key

if not gemini_api_key:
    raise ValueError("Please provide your GOOGLE_API_KEY.")
if not exchange_rate_api_key:
    raise ValueError("Please provide your EXCHANGE_RATE_API_KEY.")

llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash", 
    google_api_key=gemini_api_key, 
    temperature=0.1
)


# Define Tools
@tool
def get_stock_price(symbol: str) -> str:
    """Get the current stock price and basic info for a given stock symbol (e.g., AAPL for Apple)."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")
        current_price = hist['Close'].iloc[-1] if not hist.empty else "N/A"
        return f"Symbol: {symbol}\nCurrent Price: ${current_price:.2f}\nMarket Cap: ${info.get('marketCap', 'N/A'):,}\n52-Week High: ${info.get('fiftyTwoWeekHigh', 'N/A'):.2f}\n52-Week Low: ${info.get('fiftyTwoWeekLow', 'N/A'):.2f}"
    except Exception as e:
        return f"Error fetching data for {symbol}: {str(e)}"

@tool
def get_bond_yield() -> str:
    """Get the current yield for the 10-year US Treasury note as a bond market indicator."""
    try:
        # Using yfinance for ^TNX (10-year Treasury Note Yield)
        ticker = yf.Ticker("^TNX")
        hist = ticker.history(period="1d")
        current_yield = hist['Close'].iloc[-1] if not hist.empty else "N/A"
        return f"10-Year Treasury Note Yield: {current_yield:.2f}%\nDate: {datetime.now().strftime('%Y-%m-%d')}"
    except Exception as e:
        return f"Error fetching bond yield: {str(e)}"

@tool
def get_mutual_fund_info(symbol: str) -> str:
    """Get the current NAV and info for a mutual fund."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="7d")
        if hist.empty:
            return f"No price data available for {symbol}."
        current_price = hist['Close'].iloc[-1]

        fast_info = getattr(ticker, "fast_info", {})
        week_high = getattr(fast_info, "year_high", None)
        week_low = getattr(fast_info, "year_low", None)

        fund_name = getattr(ticker, "get_info", lambda: {})().get("longName", symbol)

        high_str = f"${week_high:.2f}" if week_high else "N/A"
        low_str = f"${week_low:.2f}" if week_low else "N/A"

        return (
            f"Mutual Fund: {symbol}\n"
            f"Current NAV: ${current_price:.2f}\n"
            f"Fund Name: {fund_name}\n"
            f"52-Week High: {high_str}\n"
            f"52-Week Low: {low_str}"
        )
    except Exception as e:
        return f"Error fetching mutual fund data for {symbol}: {str(e)}"


@tool
def get_etf_info(symbol: str) -> str:
    """Get the current price and basic info for an ETF (e.g., SPY for SPDR S&P 500 ETF)."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")
        current_price = hist['Close'].iloc[-1] if not hist.empty else "N/A"
        return f"ETF: {symbol}\nCurrent Price: ${current_price:.2f}\nFund Name: {info.get('longName', 'N/A')}\n52-Week High: ${info.get('fiftyTwoWeekHigh', 'N/A'):.2f}\n52-Week Low: ${info.get('fiftyTwoWeekLow', 'N/A'):.2f}"
    except Exception as e:
        return f"Error fetching ETF data for {symbol}: {str(e)}"


@tool
def get_usd_strength():
    """Get the current strength of the US Dollar against major currencies (EUR, JPY, GBP)."""
    try:
        url = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,JPY,GBP"
        response = requests.get(url)
        data = response.json()

        if "rates" in data:
            rates = data["rates"]
            return (
                f"USD Exchange Rates:\n"
                f"EUR: {rates.get('EUR','N/A')}\n"
                f"JPY: {rates.get('JPY','N/A')}\n"
                f"GBP: {rates.get('GBP','N/A')}\n"
                f"Date: {data.get('date', datetime.now().strftime('%Y-%m-%d'))}"
            )
        else:
            return "Error: Unable to fetch exchange rate data."
    except Exception as e:
        return f"Error fetching USD exchange rates: {str(e)}"

@tool
def get_market_news(query: str = "finance") -> str:
    """Fetch the latest financial news (stocks, bonds, ETFs, currencies)."""
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:5]
        news = []
        for item in items:
            title = item.title.text
            link = item.link.text
            pub_date = item.pubDate.text
            news.append(f"📰 {title}\n🔗 {link}\n📅 {pub_date}\n")
        return "\n".join(news)
    except Exception as e:
        return f"Error fetching news: {str(e)}"


tools = [get_stock_price, get_bond_yield, get_mutual_fund_info, get_etf_info, get_usd_strength, get_market_news]

system_prompt = """
You are FinAdvisor, a seasoned financial advisor with over 20 years of experience in investment banking and wealth management.
Your backstory: You started at Goldman Sachs, advising high-net-worth individuals through market booms and crashes, with expertise in stocks, bonds, mutual funds, ETFs, and currency markets. You prioritize diversified portfolios, risk management, and long-term growth over speculative gains. You are ethical, transparent, and always remind users that advice is not personalized—consult a professional.

When given an investment amount, suggest a diversified allocation. Use tools to fetch real-time data:
- Stocks: Always Use get_stock_price (e.g., AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, JPM, V, UNH) to get current prices and market cap.
- Bonds: Always Use get_bond_yield for 10-year Treasury yield to gauge bond market conditions.
- Mutual Funds: Always Use get_mutual_fund_info (e.g., VTSAX, FSKAX, SWPPX, VFIAX, FXAIX, VBMFX) to get NAV and fund info.
- ETFs: Always Use get_etf_info (e.g., SPY, VOO, QQQ, IWM, EFA, EEM) to get current prices.
- USD/Cash: Always Use get_usd_strength to provide currency context.
- Market Insights: Always Use get_market_news with querries for multiple asset classes(e.g., "stocks", "bonds", "ETFs", "currencies") to provide current market sentiment.

Provide:
1. Market insights (use get_market_news) with queries for multiple asset classes (e.g., "stocks", "bonds", "ETFs", "currencies").
2. Suggested investments with allocations based on the amount.
3. Provide a dynamic portfolio allocation (percentages and dollar amounts) tailored to the user's risk tolerance (low, medium, high). 
3. Risk level (low/medium/high) and rationale.
4. Real-time data for 1-2 examples per asset class (e.g., AAPL for stocks, VTSAX for mutual funds).

⚠️ VERY IMPORTANT:
- Always present the final portfolio allocation in a **valid Markdown table** with these exact columns:
| Asset Class | Allocation (%) | Dollar Amount | Rationale |
- Always include the header separator row (---).
- Do not leave blank rows.
- Complete the table before ending the response.

Keep formatting clean:
- Use single newlines (\n) between sections.
- Do not add double newlines.

End with a disclaimer: 'This advice is general and not personalized. Consult a certified financial advisor before investing.'

Keep responses concise, actionable, and engaging. End with a disclaimer: 'This advice is general and not personalized. Consult a certified financial advisor before investing.'
"""

prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=system_prompt),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Create the Agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# Main Interaction Loop
def run_financial_agent():
    print("Welcome to FinAdvisor! I'm here to provide real-time investment insights.")
    investment_amount = input("Enter the amount you want to invest (e.g., 10000): ").strip()
    risk_tolerance = input("Enter your risk tolerance (low, medium, high): ").strip().lower()
    try:
        amount = float(investment_amount)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        print("Invalid amount. Please enter a positive number.")
        return

    query = (f"I want to invest ${amount:,.2f}. "
            f"My risk tolerance is {risk_tolerance}. "
            "Please provide a dynamic portfolio allocation across stocks, bonds, ETFs, mutual funds, and cash. "
            'For each asset class(stocks, bonds, ETFs, mutual funds, cash), provide 1-2 real-time data examples with current prices and relevant data using the tools. '
            "Adjust the allocation percentages to match my risk profile and maximize expected return given current market conditions. "
            "Show percentages and dollar allocations, and provide reasoning with real-time data.")
    
    response = agent_executor.invoke({"input": query})

    final_output = response['output'].replace("\n\n", "\n")
    print("\n" + "="*50)
    print("FinAdvisor's Advice:")
    print(render_table(final_output.strip()))
    print("="*50)
    
if __name__ == "__main__":
    run_financial_agent()