import streamlit as st
import requests
import json
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Playwright Test Script Refiner",
    page_icon="🎭",
    layout="wide"
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
    .stAlert {
        margin-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🎭 Playwright Test Script Refiner</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Option to load from config.json or manual input
    config_method = st.radio(
        "Configuration Method",
        ["Load from config.json", "Manual Input"]
    )
    
    if config_method == "Load from config.json":
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                GOOGLE_API_KEY = config.get("google_api_key", "")
                MODEL_NAME = config.get("model_name", "gemini-2.0-flash")
                st.success("✅ Config loaded successfully!")
            except Exception as e:
                st.error(f"❌ Error loading config: {str(e)}")
                GOOGLE_API_KEY = ""
                MODEL_NAME = "gemini-2.0-flash"
        else:
            st.warning("⚠️ config.json not found. Please use Manual Input.")
            GOOGLE_API_KEY = ""
            MODEL_NAME = "gemini-2.0-flash"
    else:
        GOOGLE_API_KEY = st.text_input(
            "Google API Key",
            type="password",
            help="Enter your Google Gemini API key"
        )
        MODEL_NAME = st.text_input(
            "Model Name",
            value="gemini-2.0-flash",
            help="Enter the Gemini model name"
        )
    
    st.markdown("---")
    st.markdown("### 📝 Output Settings")
    output_filename = st.text_input(
        "Output Filename",
        value="refined_chatbot.py",
        help="Name for the refined script file"
    )

# Main content area
col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 Auto-Generated Test Script")
    generated_script = st.text_area(
        "Paste your auto-generated Playwright Python test script here:",
        height=400,
        placeholder="Your auto-generated Playwright Python test script goes here...",
        key="generated_script"
    )

with col2:
    st.subheader("🎬 Playwright Codegen Interactions")
    playwright_codegen_interactions = st.text_area(
        "Paste your Playwright Codegen interactions here:",
        height=400,
        placeholder="Your Playwright Codegen interactions go here...",
        key="codegen_interactions"
    )

# Refine button
st.markdown("---")
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])

with col_btn2:
    refine_button = st.button("🚀 Refine Test Script", type="primary", use_container_width=True)

# Process refinement
if refine_button:
    # Validation
    if not GOOGLE_API_KEY:
        st.error("❌ Please provide a Google API Key in the sidebar.")
    elif not generated_script.strip():
        st.error("❌ Please provide the auto-generated test script.")
    elif not playwright_codegen_interactions.strip():
        st.error("❌ Please provide the Playwright Codegen interactions.")
    else:
        with st.spinner("🔄 Refining your test script with Gemini AI..."):
            # Create the refine prompt
            refine_prompt = f"""
You are an expert QA automation assistant specializing in Playwright.

Your task is to take the **auto-generated test script** below and refine it 
according to the **Playwright Codegen interactions** that follow.

1. Review the interactions through playwright codegen for the website. Go through the steps carefully and thoroughly.
2. Compare the codegen interactions with the auto-generated test script.
3. Fix the auto-generated test script to ensure it accurately reflects the interactions recorded by Playwright Codegen.
4. Fix the selectors in the auto-generated test script to match those used in the codegen interactions.
5. For example if any website requires redirection to another page, make sure the auto-generated test script also includes that redirection step. Match this with the codegen interactions.
6. There should be no errors for waiting for elements to be visible. 
7. Maintain Playwright best practices:
   - Use `expect()` assertions where relevant.
   - Include comments for clarity (e.g., `# Step 1: Login`, `# Step 2: Navigate to Dashboard`).
   - Format cleanly and consistently using Playwright's Python style.
   - Use to_be_visible(), to_have_text(), and other relevant expect methods for assertions.
   - Add print statements to indicate success or failure of key steps.
   - Add to_be_visible() check before interacting with each element such as clicking, filling etc.
   - Add .click() after filling input fields and also before filling if that is part of the interaction.
    - Add .press("Enter") after filling input fields if that is part of the interaction.
   - Add timeouts between steps such as search and clicking and viewing results to ensure the page has loaded.
   - Instead of adding wait_for_load_state(networkidle), use wait_for_load_state("domcontentloaded") for safe side where it requires waiting for page to load.
8. Make sure the final script is syntactically correct and ready to run. 
9. If you add any comments or explanations, make sure they are relevant and concise and they are in the form of code comments.
10. Remove ```python``` tags or comments if present.


---
Auto-generated test script:
{generated_script}

---
Playwright Codegen interactions:
{playwright_codegen_interactions}

---
Now produce the corrected and refined **Playwright Python test script** ready to run.
"""

            # Gemini API URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Payload for Gemini API
            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": refine_prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 8192,
                    "responseMimeType": "text/plain"
                }
            }
            
            # Send request to Gemini
            try:
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    try:
                        reply_json = response.json()
                        reply = reply_json["candidates"][0]["content"]["parts"][0]["text"]
                        
                        # Save to file
                        with open(output_filename, "w", encoding="utf-8") as f:
                            f.write(reply.strip())
                        
                        # Display success message
                        st.success(f"✅ Refined script saved successfully to: **{output_filename}**")
                        
                        # Display the refined script
                        st.markdown("---")
                        st.subheader("🎉 Refined Test Script")
                        
                        # Create tabs for viewing and downloading
                        tab1, tab2 = st.tabs(["📖 View Script", "📥 Download"])
                        
                        with tab1:
                            st.code(reply.strip(), language="python", line_numbers=True)
                        
                        with tab2:
                            st.download_button(
                                label="⬇️ Download Refined Script",
                                data=reply.strip(),
                                file_name=output_filename,
                                mime="text/x-python",
                                use_container_width=True
                            )
                            
                            st.info(f"💾 Script also saved locally as: {output_filename}")
                    
                    except Exception as e:
                        st.error(f"❌ Error parsing Gemini response: {str(e)}")
                        with st.expander("🔍 View Raw Response"):
                            st.text(response.text)
                
                else:
                    st.error(f"❌ API Error {response.status_code}")
                    with st.expander("🔍 View Error Details"):
                        st.text(response.text)
            
            except Exception as e:
                st.error(f"❌ Request failed: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <p>🎭 Playwright Test Script Refiner | Powered by Google Gemini AI</p>
        <p style='font-size: 0.8rem;'>Automatically refines auto-generated test scripts using Playwright Codegen interactions</p>
    </div>
""", unsafe_allow_html=True)