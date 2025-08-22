import asyncio
import re
from groq import Groq
from playwright.async_api import async_playwright

# Configure Groq API
GROQ_API_KEY = "Enter your Groq API key here"
groq_client = Groq(api_key=GROQ_API_KEY)

class GroqOSSAgent:
    """Base agent class using Groq models"""
    def __init__(self, name: str, system_message: str, model_name: str):
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
        model_name="deepseek-r1-distill-llama-70b"
    )
    return await refiner.generate_response(instruction)

class SiteInspectorAgent(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are a site inspector that analyzes web pages to extract reliable Playwright locators.
        Use the browse_page tool to fetch the page, then summarize key elements' selectors (ID, name, Class Name, Tag Name like div, span etc, CSS selector and XPath) for the user's instruction.
        Focus on the elements specified in the instruction given by the user.
        Output a string of 'Recommended Locators: [list them here]' to append to the instruction.
        If the site has dynamic parts, suggest waits and unique selectors.
        If no URL is provided, generate generic but reliable locators based on the described elements and common web patterns. Also suggest self-healing locator strategies.
        Moreover, if no URL is provided, make sure you generate reliable Playwright locators for the key elements based on common web patterns and instruction provided by the user.
        Use Playwright's capabilities to ensure the locators are robust and adaptable to changes in the page structure.
        Ensure the locators are:
        - Reliable and stable
        - Adaptable to dynamic content
        - Use self-healing strategies where possible
        - Include ID, name, class name, tag name, CSS selector, XPath, and role-based selectors
        - Use text-based selectors where applicable
        - Prioritize selectors based on reliability and stability

        """
        super().__init__("SiteInspector", system_message, model_name="deepseek-r1-distill-llama-70b")

    async def fetch_html(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            await browser.close()
            return html

    async def inspect_site(self, url: str, key_elements: str) -> str:
        if url:
            browse_prompt = f"Extract HTML structure and Playwright locators for {key_elements} on {url}."
            html_content = await self.fetch_html(url)  
            tool_result = await self.generate_response(
                f"URL: {url}\nElements: {key_elements}\nHTML Snippet:\n{html_content[:5000]}"
            )
            return await self.generate_response(
                f"URL: {url}\nElements: {key_elements}\nTool Result: {tool_result}"
            )
        else:
            # Generate generic locators when no URL is provided
            return await self.generate_response(
                f"No URL provided. Generate reliable Playwright locators for {key_elements} based on common web patterns and instructions provided in the prompt."
            )

class PlannerAgentOSS(GroqOSSAgent):
    def __init__(self):
        system_message = """
        You are an expert QA test planner with deep NLP understanding.
        Your goal is to generate comprehensive test cases covering all possible variations, including but not limited to:
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

        Analyze the provided instruction and generate test cases for as many of these types as applicable. If a type doesn't apply, skip it but aim to cover all possible variations where relevant.
        Prioritize generating multiple test cases per type to cover variations (e.g., different inputs, scenarios).
        For each test case, include:
        - Test Case Name (Indicate type, e.g., Functional - Login Success)
        - Description (Functionality being tested, including all the possible variations)
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
        - Use the provided instruction, refined details, and locator recommendations as context for generating test cases
        - For performance/security/usability, adapt to Playwright capabilities (e.g., measure page load time, check for alerts, verify ARIA attributes)
        - For exploratory, generate test cases with randomized or varied inputs to simulate exploration
        - Generate only the testcases in this step, dont output any refined instruction, explainations or locator recommendations.
        - Use the provided instruction, refined details, and locator recommendations as context for generating test cases
        """
        super().__init__("PlannerOSS", system_message, model_name="deepseek-r1-distill-llama-70b")

class UserProxyAgent:
    def __init__(self, name: str):
        self.name = name

    async def initiate_chat(self, agent, message: str) -> str:
        return await agent.generate_response(message)

async def main():
    print("🤖 Initializing Multi-Agent QA Planning System...\n")

    user = UserProxyAgent("User")
    inspector = SiteInspectorAgent()
    planner = PlannerAgentOSS()

    # Accept any prompt from user
    user_prompt = input("Enter your automation instruction:\n").strip()

    # Auto-detect site URL from prompt (basic regex match for http/https links)
    url_match = re.search(r'(https?://[^\s]+)', user_prompt)
    site_url = url_match.group(1) if url_match else None


    element_keywords = []
    for kw in ["search", "input", "button", "title", "heading", "section", "link", "locator", "element", "screenshot", "scroll", "verify", "assert", "check", "capture", "wait", "load", "click", "fill", "submit", "navigate", "page", "url", "text", "content", "selector", "xpath", "css", "id", "name", "class", "tag", "role", "exact", "visible", "hidden", "exists", "not exists", "error", "fail", "pass", "retry", "timeout", "sleep", "wait_for", "print", "output", "log", "debug", "info", "warn", "assertion", "asserts", "check", "checks", "validation", "validations", "test", "tests", "step", "steps", "action", "actions", 
               "interaction", "interactions", "element interaction", "element interactions", "locator strategy", "self-healing", "self healing", "dynamic", "dynamic elements", "dynamic content", "dynamic locators", "dynamic selectors", "dynamic elements strategy", "dynamic content strategy", "dynamic locators strategy", "dynamic selectors strategy"]:
        if kw in user_prompt.lower():
            element_keywords.append(kw)
    key_elements = ", ".join(element_keywords) if element_keywords else "main interactive elements"

    # Step 0: Refining user instruction
    print("Step 0: Refining user instruction...")
    refined_instruction = await refine_instruction(user_prompt)
    print("Refined Instruction:\n", refined_instruction)
    print("=" * 50)

    # Step 0.5: Inspecting site for locators (optional if no URL)
    print("Step 0.5: Inspecting site for locators...")
    locator_recommendations = await inspector.inspect_site(site_url, key_elements)
    refined_instruction += f"\n{locator_recommendations}"
    print("Locator Recommendations:\n", locator_recommendations)
    print("=" * 50)

    # Step 1: Planning test cases
    print("Step 1: Planning test cases...")
    test_cases = await user.initiate_chat(planner, refined_instruction)
    print(test_cases)
    print("=" * 50)

    print("\nTest case generation complete!")

if __name__ == "__main__":
    asyncio.run(main())