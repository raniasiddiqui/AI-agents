import streamlit as st
import asyncio
import re
from groq import Groq
from playwright.async_api import async_playwright
from urllib.parse import urlparse
from collections import deque
import json
import os
from datetime import datetime
import nest_asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

nest_asyncio.apply()

# Page configuration
st.set_page_config(
    page_title="QA Automation Suite Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        background: linear-gradient(90deg, #1f77b4 0%, #ff7f0e 100%);
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        font-weight: bold;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)

# Load configuration
@st.cache_resource
def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ config.json not found. Please create it with your API keys.")
        st.stop()

CONFIG = load_config()
GROQ_API_KEY = CONFIG.get("groq_api_key", "")
DEFAULT_GROQ_MODEL = CONFIG.get("groq_default_model", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    st.error("❌ GROQ API key not found in config.json")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)

# Agent classes (keeping your existing logic)
class GroqOSSAgent:
    def __init__(self, name: str, system_message: str, model_name: str = DEFAULT_GROQ_MODEL):
        self.name = name
        self.system_message = system_message
        self.model_name = model_name

    async def generate_response(self, message: str) -> str:
        try:
            def run_completion():
                completion = groq_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": message}
                    ]
                )
                return completion.choices[0].message.content

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_completion)
        except Exception as e:
            return f"Error generating Groq OSS response: {str(e)}"

async def refine_instruction(instruction: str) -> str:
    refiner = GroqOSSAgent(
        name="InstructionRefiner",
        system_message="""
        You are an expert in writing clear, precise, and unambiguous instructions for QA automation tasks.
        Your task is to refine the provided instruction and make it understandable by an LLM easily, to ensure it is:
        - Clear and concise, actionable language, avoiding ambiguity.
        - Unambiguous with no vague terms
        - Structured for easy interpretation by automation agents
        - Focused on specifying exact actions, selectors, and validations
        - Compliant with Playwright sync API requirements
        - Includes self-healing locator guidelines
        - Avoids placeholders or vague instructions
        - Follow Playwright sync API conventions
        - Include possible self-healing locator strategies. These include ID, name, class name, tag name, CSS selector, XPath, and role-based selectors, and text-based selectors. They should be prioritized based on reliability and stability.
        - Focus on:
          - Setup steps (navigate, prepare data)
          - Action steps (click, fill, submit)
          - Verification steps (assertions, checks)
          - Error handling considerations        
        - Requests per-step pass/fail logging and assertions
        Output only the refined instruction as plain text, no markdown or explanations. Dont output any testcases in this step.
        """,
        model_name=DEFAULT_GROQ_MODEL
    )
    return await refiner.generate_response(instruction)

class SiteInspectorAgent(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are a site inspector that analyzes crawled web pages to extract reliable Playwright locators and discover QA-relevant insights for comprehensive test case generation.
        You receive snippets from multiple crawled pages of the site and the user's instruction describing specific functionalities.
        Analyze the crawled page snippets and user instruction to:
        - Summarize the site structure, key pages, navigation flows, and discovered features (e.g., forms, buttons, interactive elements, user journeys).
        - Identify possible test scenarios based on the site's elements and the user's instruction, including core functionalities, alternative flows, edge cases, and error conditions.
        - Extract and recommend reliable Playwright locators (ID, name, class name, tag name, CSS selector, XPath, role-based, text-based) for key elements mentioned in the instruction or discovered during crawling.
        - Suggest self-healing locator strategies and waits for dynamic content, prioritizing reliability and stability.
        - Provide insights to generate a wider range of test cases, such as alternative paths, error-prone areas, and integration points.
        Output a string starting with 'Site Insights and Recommended Locators: ' followed by a structured summary:
        - Site Structure: Summarize key pages, navigation patterns, and features.
        - Discovered Test Scenarios: List potential test cases (e.g., functional, negative, edge cases) based on crawled data and instruction.
        - Recommended Locators: List reliable locators for key elements, prioritized by stability (e.g., ID > role-based > text-based > CSS/XPath).
        If no URL was crawled, generate generic but reliable locators and insights based on common web patterns and the user's instruction.
        Ensure locators are:
        - Reliable and stable
        - Adaptable to dynamic content
        - Use self-healing strategies where possible
        - Include ID, name, class name, tag name, CSS selector, XPath, and role-based selectors
        - Use text-based selectors where applicable
        - Prioritize selectors based on reliability and stability
        """
        super().__init__("SiteInspector", system_message, model_name=DEFAULT_GROQ_MODEL)

    async def crawl_site(self, start_url: str, username: str, password: str, max_pages: int = 5) -> dict:
        """Simple BFS crawler to fetch up to max_pages internal pages and their HTML snippets after logging in."""
        from collections import deque
        visited = set()
        to_visit = deque([start_url])
        page_contents = {}
        base_origin = urlparse(start_url).scheme + "://" + urlparse(start_url).netloc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            try:
                # Navigate to login page
                st.write(f"Navigating to {start_url}...")
                await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

                # Check if a "Sign In" button/link needs to be clicked
                sign_in_button = await page.query_selector("a[href*='login'], button:has-text('Sign In'), button:has-text('Log In')")
                if sign_in_button:
                    st.write("Clicking 'Sign In' button...")
                    await sign_in_button.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)

                # Selectors for email, password, and submit button. These can be expanded based on common patterns.
                email_selectors = [
                    "#userNameInput", "data-testid='email'", "input[type='email']", 
                    "input[name='email']", "input[id='email']", "//input[contains(@placeholder, 'Email')]"
                ]
                password_selectors = [
                    "#passwordInput", "data-testid='password'", "input[type='password']", 
                    "input[name='password']", "input[id='password']", "//input[contains(@placeholder, 'Password')]"
                ]
                submit_selectors = [
                    "#submitButton", ".submit", "[role='button']:has-text('Sign in')", 
                    "data-testid='submit'", "button[type='submit']", 
                    "button:has-text('Sign In')", "button:has-text('Log In')"
                ]

                email_locator = None
                for selector in email_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        email_locator = selector
                        break
                    except:
                        continue

                if not email_locator:
                    html = await page.content()
                    st.error(f"Error: No email input found. Page HTML:\n{html[:1000]}...")
                    raise Exception("No email input found with provided selectors")

                st.write(f"Filling email with selector: {email_locator}")
                await page.fill(email_locator, username)
                await page.wait_for_timeout(1000) 

                password_locator = None
                for selector in password_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        password_locator = selector
                        break
                    except:
                        continue

                if not password_locator:
                    raise Exception("No password input found with provided selectors")

                st.write(f"Filling password with selector: {password_locator}")
                await page.fill(password_locator, password)
                await page.wait_for_timeout(1000)

                submit_locator = None
                for selector in submit_selectors:
                    try:
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        submit_locator = selector
                        break
                    except:
                        continue

                if not submit_locator:
                    raise Exception("No submit button found with provided selectors")

                st.write(f"Clicking submit with selector: {submit_locator}")
                await page.click(submit_locator)

                # Wait for post-login page
                try:
                    await page.wait_for_selector(".search-panel, #searchPanel, [role='search']", state="visible", timeout=30000)
                    st.write(f"Logged in successfully at {start_url}")
                except:
                    error_selector = "text='Invalid credentials', text='Login failed', [role='alert']"
                    error_element = await page.query_selector(error_selector)
                    if error_element:
                        error_text = await error_element.inner_text()
                        st.error(f"Login failed with error: {error_text}")
                        raise Exception(f"Login failed: {error_text}")
                    await page.wait_for_timeout(5000)
                    # current_url = page.url
                    # if current_url == start_url:
                    #     html = await page.content()
                    #     st.error(f"Error: No redirect after login. Current URL: {current_url}\nPage HTML:\n{html[:1000]}...")
                    #     raise Exception("No redirect after login attempt")
                    # st.write(f"Redirected to {current_url} after login")

                # Start crawling after login
                while to_visit and len(page_contents) < max_pages:
                    current = to_visit.popleft()
                    if current in visited:
                        continue
                    visited.add(current)
                    try:
                        st.write(f"Crawling page: {current}")
                        await page.goto(current, wait_until="domcontentloaded", timeout=60000)
                        html = await page.content()
                        page_contents[current] = html[:4000] # Snippet
                        
                        new_links = await page.evaluate('''
                            (base_origin) => {
                                return Array.from(document.querySelectorAll('a[href]'))
                                    .map(a => {
                                        let href = a.getAttribute('href');
                                        if (href) {
                                            try {
                                                let fullUrl = new URL(href, window.location.href).href;
                                                if (fullUrl.startsWith(base_origin)) {
                                                    return fullUrl;
                                                }
                                            } catch (e) {}
                                        }
                                        return null;
                                    })
                                    .filter(Boolean);
                            }
                        ''', base_origin)

                        for link in new_links:
                            parsed = urlparse(link)
                            if (link not in visited and
                                link not in to_visit and
                                not any(link.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.zip')) and
                                parsed.path != '/' and parsed.path != ''):
                                to_visit.append(link)
                    except Exception as e:
                        st.write(f"Error crawling {current}: {e}")
                        continue
            except Exception as e:
                st.error(f"Error during login or crawling: {e}")
                if not page_contents:
                    try:
                        html = await page.content()
                        st.write(f"Page HTML on failure:\n{html[:1000]}...")
                    except Exception as page_e:
                        st.error(f"Could not even get page content on failure: {page_e}")
            finally:
                await context.close()
                await browser.close()
        return page_contents

    async def inspect_site(self, url: str, key_elements: str, instruction: str, username: str, password: str) -> str:
        if url:
            if not username or not password:
                st.warning("Username or password not provided in prompt. Crawling without login.")
                # Implement a non-login crawl or return generic response
                return await self.generate_response(
                    f"No login credentials provided. Generate reliable Playwright locators and insights for {key_elements} based on common web patterns and the instruction: {instruction}"
                )
                
            page_contents = await self.crawl_site(url, username, password, max_pages=5)
            if not page_contents:
                st.warning("No pages crawled successfully. Generating generic insights.")
                return await self.generate_response(
                    f"No URL content crawled. Generate reliable Playwright locators and insights for {key_elements} based on common web patterns and the instruction: {instruction}"
                )
            content_str = "\n\n---\n\n".join([f"Page: {k}\nHTML Snippet:\n{v}" for k, v in page_contents.items()])
            crawl_summary = await self.generate_response(
                f"Start URL: {url}\nKey Elements to Focus: {key_elements}\nUser Instruction: {instruction}\nCrawled Pages Snippets:\n{content_str}"
            )
            recommendations = await self.generate_response(
                f"Analyze the crawl summary for site insights and locators: {crawl_summary}\nUser Key Elements: {key_elements}\nUser Instruction: {instruction}"
            )
            return recommendations
        else:
            st.warning("No URL provided. Generating generic insights.")
            return await self.generate_response(
                f"No URL provided. Generate reliable Playwright locators, self-healing strategies, and generic site insights (e.g., common flows for {key_elements}) based on common web patterns and the instruction: {instruction}"
            )

class PlannerAgentOSS(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are an expert QA test planner with deep NLP understanding.
        Your goal is to generate comprehensive test cases covering all possible variations, including but not limited to:

        IMPORTANT: 
        Firstly, your priority is to generate test cases for the core functionalities described in the instruction, including insights from crawled site data.
        The core functionalities include covering complete flows for each feature mentioned in the instruction and discovered during site crawling.
        The features are the basic flow, alternative flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction, and additional scenarios from crawled data.
        Then, expand to cover edge cases, error handling, and less common scenarios. First cpver the core functionalities in detail which mainly includes basic flow, alternate flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction.
        Then cover test cases discovered during site crawling as well. Then cover edge cases, error handling, and less common scenarios.
        
        After completing the core functionalities, generate test cases for the following types:
        - Functional (positive scenarios where the system works as expected)
        - Negative (invalid inputs, error handling, failures)
        - Boundary (edge cases like min/max values, limits)
        - Performance (load times, responsiveness under stress; simulate with Playwright where possible, e.g., multiple interactions, timeouts)
        - Security (vulnerabilities like injection, authentication bypass; automate checks for common issues like XSS, CSRF if detectable via UI)
        - Integration (interactions between components, APIs if accessible via UI)
        - Usability (UI/UX checks like accessibility, responsiveness, user flows; use Playwright for visibility, focus, etc.)
        - Regression (re-testing core functionalities to ensure no breaks)
        - Smoke (basic functionality checks to verify build stability)
        - Sanity (quick checks on specific changes or fixes)
        - Database (if applicable, verify data persistence, queries via UI interactions)
        - End-to-End (full user journeys from start to finish)
        - Exploratory (suggest automated heuristics or random inputs for discovery; adapt to automation where feasible)

        Analyze the provided instruction, refined details, and site insights/locator recommendations to generate test cases for as many of these types as applicable. If a type doesn't apply, skip it but aim to cover all possible variations where relevant.
        Prioritize generating multiple test cases per type to cover variations (e.g., different inputs, scenarios).
        For each test case, include:
        - Test Case Name (Indicate type, e.g., Functional - Login Success)
        - Description (Functionality being tested, including all possible variations)
        - Preconditions (Setup required, e.g., browser state, data)
        - Test Case Details (High-level overview)
        - Step-by-step actions with clear selectors, actions, and validations (Use Playwright sync API, self-healing locators, waits, per-step logging/assertions)
        - Expected Result (Clear pass/fail criteria)

        Structure your response with sections for each test type (e.g., ## Functional Test Cases, ## Negative Test Cases, etc.).
        Under each section, provide a numbered list of test cases.
        Use precise language and avoid ambiguity.
        Focus on:
        - Setup steps (navigate, prepare data)
        - Action steps (click, fill, submit)
        - Verification steps (assertions, checks)
        - Error handling considerations
        - Use clear, actionable language
        - Output only the test cases, no explanations or markdown beyond the required section headers and numbered lists
        - Follow Playwright sync API conventions
        - Use self-healing locator strategies (e.g., ID, name, class name, tag name, CSS selector, XPath, role-based selectors, text-based selectors)
        - Prioritize selectors based on reliability and stability
        - Include self-healing locator strategies (e.g., role-based, text-based over IDs if dynamic)
        - Ensure each test case is executable with clear pass/fail criteria
        - Include per-step pass/fail logging and assertions (e.g., console.log('Step 1: Passed') or expect().toBeVisible())
        - Use the provided instruction, refined details, and locator recommendations/site insights as context for generating test cases
        - For performance/security/usability, adapt to Playwright capabilities (e.g., measure page load time, check for alerts, verify ARIA attributes)
        - For exploratory, generate test cases with randomized or varied inputs to simulate exploration
        - Generate only the test cases, no explanations or markdown beyond the required section headers and numbered lists
        - Use the provided instruction, refined details, and locator recommendations as context for generating test cases
        - First generate testcases for core functionalities which mainly includes basic flow, alternate flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction.
        - Then expand to cover all other types of testcases as mentioned above.
        """
        super().__init__("PlannerOSS", system_message, model_name=DEFAULT_GROQ_MODEL)

class TestCodeGenerator(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are an expert in generating executable Python scripts for QA automation using Playwright sync API.
        Given a test case description with name, description, preconditions, details, steps, expected result, and using the locator recommendations from the context.
        Determine if it is possible to automate. If the test case requires manual intervention, special simulation like network throttling for performance, or interacting with the database, or something not easily done with Playwright UI automation, respond with 'Not Automatable'.
        If automatable, generate a complete standalone Python script that:
        - Imports from playwright.sync_api import sync_playwright, expect
        - Uses with sync_playwright() as p:
        - Launches browser = p.chromium.launch(headless=True)
        - Creates context = browser.new_context()
        - Creates page = context.new_page()
        - Implements the preconditions and steps using the selectors from the context or recommended locators.
        - Use either the provided selectors or self-healing locator strategies (ID, name, class name, tag name, CSS selector, XPath, role-based selectors, text-based selectors) prioritized by reliability and stability
        - Uses page.goto, page.fill, page.click, page.wait_for_selector, etc.
        - For validations, use expect(page.locator(selector)).to_be_visible(), to_have_text(), etc.
        - If all assertions pass, print "Test Passed"
        - If any fails, catch exception and print "Test Failed: [reason]"
        - Include error handling with try-except.
        - Use the username and password from the prompt. If any test case requires login, include the login steps using the provided credentials.
        - Ensure the script is executable as a standalone file.
        - Use the url from the prompt.
        - Use self-healing locators as per guidelines.
        - Ensure the python script follows Playwright sync API conventions and is free of syntax errors.
        - For each step, include per-step pass/fail logging and assertions.
        - Please make sure that if you add any comments or explainations or notes, they are in the form of python comments only.
        Output only the Python script as plain text if automatable, or 'Not Automatable'.
        """
        super().__init__("TestCodeGenerator", system_message, model_name=DEFAULT_GROQ_MODEL)

def clean_generated_code(code: str) -> str:
    code = re.sub(r"```[a-zA-Z]*", "", code)
    cleaned_lines = []
    for line in code.splitlines():
        if re.match(r"^\s*(#|from |import |with |def |class |try|except|page\.|browser|context|print|expect)", line):
            cleaned_lines.append(line)
        elif line.strip().startswith(("Test Case", "<think>", "###", "Alright")):
            continue
        elif line.strip() == "":
            continue
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

async def run_automation_pipeline(user_prompt: str, site_url: str, username: str, password: str, status_container):
    try:
        # Extract keywords
        element_keywords = []
        for kw in ["search", "input", "button", "title", "heading", "section", "link", "locator", "element", "screenshot", 
                   "scroll", "verify", "assert", "check", "capture", "wait", "load", "click", "fill", "submit", "navigate", 
                   "page", "url", "text", "selector", "xpath", "css", "id", "name", "class", "tag", "role"]:
            if kw in user_prompt.lower():
                element_keywords.append(kw)
        key_elements = ", ".join(element_keywords) if element_keywords else "main interactive elements"

        # Step 1: Refine instruction
        status_container.info("🔄 Step 1/4: Refining instruction...")
        refined_instruction = await refine_instruction(user_prompt)
        status_container.success("✅ Step 1/4: Instruction refined")
        with st.expander("📝 View Refined Instruction"):
            st.text(refined_instruction)

        # Step 2: Inspect site
        status_container.info("🔍 Step 2/4: Inspecting site and extracting locators...")
        crawl_status = st.empty()
        
        def update_crawl_status(msg):
            crawl_status.text(msg)
        
        inspector = SiteInspectorAgent()
        locator_recommendations = await inspector.inspect_site(
            site_url, key_elements, user_prompt, username, password, 
            # status_callback=update_crawl_status
        )
        refined_instruction += f"\n{locator_recommendations}"
        status_container.success("✅ Step 2/4: Site inspection complete")
        with st.expander("🔍 View Site Insights"):
            st.text(locator_recommendations)


        # Step 3: Generate test cases
        status_container.info("📋 Step 3/4: Planning test cases...")
        planner = PlannerAgentOSS()
        test_cases_text = await planner.generate_response(refined_instruction)
        status_container.success("✅ Step 3/4: Test cases generated")
        
        # Parse test cases
        pattern = re.compile(
            r'(?:(?:###\s*\d+\.\s*)?(.*?)\n)?'
            r'(?:\*\*Description\*\*:\s*(.*?)\n)?'
            r'(?:\*\*Preconditions\*\*:\s*(.*?)\n)?'
            r'(?:\*\*Test Case Details\*\*:\s*(.*?)\n)?'
            r'(?:\*\*Steps\*\*:\s*(.*?))?'
            r'(?:\*\*Expected Result\*\*:\s*(.*?))?(?=\n###|\n##|$)',
            re.DOTALL | re.MULTILINE
        )

        test_cases_list = []
        for match in pattern.finditer(test_cases_text):
            if not any(match.groups()):
                continue
            test_cases_list.append({
                'name': (match.group(1) or "").strip(),
                'description': (match.group(2) or "").strip(),
                'preconditions': (match.group(3) or "").strip(),
                'details': (match.group(4) or "").strip(),
                'steps': (match.group(5) or "").strip(),
                'expected': (match.group(6) or "").strip()
            })

        with open("test_cases.json", "w", encoding="utf-8") as f:
            json.dump(test_cases_list, f, indent=2, ensure_ascii=False)

        with st.expander(f"📋 View Generated Test Cases ({len(test_cases_list)} total)"):
            st.json(test_cases_list)

        # Step 4: Generate unified script
        status_container.info("💻 Step 4/4: Generating unified test suite...")
        
        all_cases_text = ""
        for idx, tc in enumerate(test_cases_list):
            all_cases_text += (
                f"\n### Test Case {idx+1}: {tc['name']}\n"
                f"Description: {tc['description']}\n"
                f"Preconditions: {tc['preconditions']}\n"
                f"Details: {tc['details']}\n"
                f"Steps: {tc['steps']}\n"
                f"Expected Result: {tc['expected']}\n"
                "---------------------------------------------\n"
            )

        unified_message = f"""
You are an expert QA automation engineer.

Generate a **single unified Python Playwright script** that executes ALL the following test cases in one continuous flow.

Requirements:
- Use `with sync_playwright() as p:` once.
- Launch browser only once (headless=True).
- Reuse same `context` and `page`.
- If login is required, perform it once at the start.
- Implement each test case sequentially with try/except blocks.
- After each test, print "✅ Test Passed - [Test Name]" or "❌ Test Failed - [Test Name]: [error]".
- Even if one test fails, continue executing the rest.
- Close the browser at the end.
- Use self-healing locator strategies (ID, name, class name, tag name, CSS selector, XPath, role-based selectors, text-based selectors) prioritized by reliability and stability.
- Cover all possible flows for each feature mentioned in the instruction and discovered during site crawling.
- The features are the basic flow, alternative flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction, and additional scenarios from crawled data.
- First cover the core functionalities in detail which mainly includes basic flow, alternate flow, pre-conditions, post-conditions, validations/rules mentioned in the instruction.
- Then cover test cases discovered during site crawling as well.
- Then cover edge cases, error handling, and less common scenarios.
- Use provided URL: {site_url}
- Username: {username or 'N/A'}
- Password: {password or 'N/A'}
- Make sure there are no syntax errors.
- Make sure if you add any comments or explainations or notes or additional paragraphs, they are in the form of python comments only.

Here are the test cases:
{all_cases_text}

Locator Recommendations and Context:
{refined_instruction}
{user_prompt}
"""

        generator = TestCodeGenerator()
        code = await generator.generate_response(unified_message)
        cleaned_code = clean_generated_code(code)
        
        with open("combined_test_suite.py", "w", encoding="utf-8") as f:
            f.write(cleaned_code)

        status_container.success("✅ Step 4/4: Unified test suite generated successfully!")
        
        return test_cases_text, cleaned_code, test_cases_list

    except Exception as e:
        status_container.error(f"❌ Error: {str(e)}")
        st.exception(e)
        return None, None, None

# Main UI
def main():
    st.markdown('<p class="main-header">🤖 QA Automation Suite Generator</p>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    <b>Welcome to the QA Automation Suite Generator!</b><br>
    This tool helps you automatically generate comprehensive test cases and Playwright automation scripts from natural language instructions.
    </div>
    """, unsafe_allow_html=True)

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.info(f"**Model:** {DEFAULT_GROQ_MODEL}")
        
        st.markdown("---")
        st.header("📚 How to Use")
        st.markdown("""
        1. Enter your automation instruction
        2. Provide the target URL
        3. Add credentials if login is required
        4. Click 'Generate Test Suite'
        5. Review and download the generated code
        """)
        
        st.markdown("---")
        st.header("ℹ️ About")
        st.markdown("""
        This tool uses AI to:
        - Crawl and analyze websites
        - Generate comprehensive test cases
        - Create executable Playwright scripts
        - Support self-healing locators
        """)

    # Main input form
    with st.form("automation_form"):
        st.subheader("📝 Automation Details")
        
        user_prompt = st.text_area(
            "Automation Instruction",
            placeholder="Example: Test login functionality on https://example.com with username='testuser' and password='testpass123'",
            height=120,
            help="Describe what you want to test. Include URL and credentials if needed."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            site_url = st.text_input(
                "Target URL",
                placeholder="https://example.com",
                help="The website URL to test"
            )
        
        with col2:
            max_pages = st.number_input(
                "Max Pages to Crawl",
                min_value=1,
                max_value=20,
                value=5,
                help="Number of pages to crawl for site analysis"
            )
        
        col3, col4 = st.columns(2)
        with col3:
            username = st.text_input(
                "Username",
                placeholder="testuser",
                help="Username for login (if required)"
            )
        
        with col4:
            password = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
                help="Password for login (if required)"
            )
        
        submit_button = st.form_submit_button("🚀 Generate Test Suite", use_container_width=True)

    # Process form submission
    if submit_button:
        if not user_prompt:
            st.error("❌ Please enter an automation instruction")
            return
        
        # Extract URL from prompt if not provided separately
        if not site_url:
            url_match = re.search(r'(https?://[^\s]+)', user_prompt)
            site_url = url_match.group(1) if url_match else None
        
        # Extract credentials from prompt if not provided separately
        if not username:
            username_match = re.search(r"username\s*=\s*'([^']+)'", user_prompt)
            username = username_match.group(1) if username_match else ""
        
        if not password:
            password_match = re.search(r"password\s*=\s*'([^']+)'", user_prompt)
            password = password_match.group(1) if password_match else ""
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_container = st.empty()
        
        # Run the automation pipeline
        with st.spinner("Processing..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            test_cases_text, cleaned_code, test_cases_list = loop.run_until_complete(
                run_automation_pipeline(user_prompt, site_url, username, password, status_container)
            )
            
            progress_bar.progress(100)
        
        if cleaned_code:
            st.markdown("---")
            st.markdown('<div class="step-header">🎉 Generation Complete!</div>', unsafe_allow_html=True)
            
            # Display results in tabs
            tab1, tab2, tab3 = st.tabs(["📄 Test Cases", "💻 Generated Code", "📊 Summary"])
            
            with tab1:
                st.subheader(f"Generated Test Cases ({len(test_cases_list)} total)")
                
                # Search and filter
                search_term = st.text_input("🔍 Search test cases", placeholder="Type to filter...")
                
                filtered_cases = test_cases_list
                if search_term:
                    filtered_cases = [
                        tc for tc in test_cases_list 
                        if search_term.lower() in tc.get('name', '').lower() or 
                           search_term.lower() in tc.get('description', '').lower()
                    ]
                
                st.info(f"Showing {len(filtered_cases)} of {len(test_cases_list)} test cases")
                
                for idx, tc in enumerate(filtered_cases, 1):
                    with st.expander(f"**{idx}. {tc.get('name', 'Unnamed Test')}**"):
                        st.markdown(f"**Description:** {tc.get('description', 'N/A')}")
                        st.markdown(f"**Preconditions:** {tc.get('preconditions', 'N/A')}")
                        st.markdown(f"**Details:** {tc.get('details', 'N/A')}")
                        st.markdown(f"**Steps:**\n{tc.get('steps', 'N/A')}")
                        st.markdown(f"**Expected Result:** {tc.get('expected', 'N/A')}")
                
                # Download test cases as JSON
                st.download_button(
                    label="📥 Download Test Cases (JSON)",
                    data=json.dumps(test_cases_list, indent=2, ensure_ascii=False),
                    file_name=f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            with tab2:
                st.subheader("Generated Playwright Test Suite")
                
                # Code editor with syntax highlighting
                st.code(cleaned_code, language="python", line_numbers=True)
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.download_button(
                        label="📥 Download Test Suite (.py)",
                        data=cleaned_code,
                        file_name=f"combined_test_suite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py",
                        mime="text/x-python"
                    )
                
                with col2:
                    if st.button("📋 Copy to Clipboard"):
                        st.info("Code copied! (use Ctrl+C on the code block)")
                
                # Instructions
                st.markdown("---")
                st.markdown("### 🚀 How to Run")
                st.code("""
# Install Playwright if not already installed
pip install playwright
playwright install

# Run the generated test suite
python combined_test_suite.py
                """, language="bash")
            
            with tab3:
                st.subheader("📊 Generation Summary")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Test Cases", len(test_cases_list))
                with col2:
                    st.metric("Code Lines", len(cleaned_code.splitlines()))
                with col3:
                    st.metric("Target URL", "✓" if site_url else "✗")
                
                st.markdown("---")
                
                # Categorize test cases by type
                test_types = {}
                for tc in test_cases_list:
                    name = tc.get('name', '')
                    # Extract test type from name (e.g., "Functional - Login Success")
                    if ' - ' in name:
                        test_type = name.split(' - ')[0].strip()
                    else:
                        test_type = "General"
                    
                    test_types[test_type] = test_types.get(test_type, 0) + 1
                
                if test_types:
                    st.subheader("Test Case Distribution")
                    for test_type, count in sorted(test_types.items(), key=lambda x: x[1], reverse=True):
                        st.markdown(f"**{test_type}:** {count} test case(s)")
                
                st.markdown("---")
                st.markdown("### ✅ Next Steps")
                st.markdown("""
                1. Review the generated test cases and code
                2. Download the test suite
                3. Customize as needed for your specific requirements
                4. Install Playwright if not already installed
                5. Run the test suite and review results
                6. Integrate into your CI/CD pipeline
                """)
                
                # Session info
                st.markdown("---")
                st.info(f"""
                **Generation Details:**
                - Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                - Model: {DEFAULT_GROQ_MODEL}
                - Target URL: {site_url or 'Not specified'}
                - Login Required: {'Yes' if username and password else 'No'}
                """)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem 0;">
        <p>🤖 Powered by Groq AI & Playwright | Built with Streamlit</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()