from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="FSD Generator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        height: 3em;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #45a049;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .success-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .header-container {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
    }
    .step-indicator {
        display: flex;
        justify-content: center;
        margin: 2rem 0;
        gap: 1rem;
    }
    .step {
        padding: 0.5rem 1.5rem;
        border-radius: 20px;
        background-color: #e9ecef;
        font-weight: 600;
    }
    .step-active {
        background-color: #667eea;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Gemini client
@st.cache_resource
def get_gemini_client():
    return OpenAI(
        api_key="YOUR_GEMINI_API_KEY_HERE",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

gemini = get_gemini_client()

class StandardSchema(BaseModel):
    understood: bool
    feedback: str
    output: str

fsd_system_prompt = """
You are a Senior Business Analyst responsible for verifying whether a software description
contains enough clarity to begin generating a Functional Specifications Document (FSD).

IMPORTANT RULES:
- Do NOT require the user to provide a fully detailed specification.
- Do NOT reject descriptions just because information is missing (e.g., platform, auth, UI/UX).
- Missing information will be handled later using [TBD] and [Assumption].

Your job is ONLY to check:
1. The description gives at least some functional intent (what the system does or what problem it solves).
2. Reject ONLY if:
   - The input is nonsense,
   - Or too ambiguous to understand the purpose.

If rejecting:
- Politely ask the user to briefly describe what the software does.

If accepting:
- Summarize the description in a structured way for the FSD generator.
- Do NOT fill in missing information; leave that to the next step.

Respond strictly in the format:

"understood": true/false
"feedback": Message to user (empty if understood=true)
"output": Structured summary (only when understood=true)
"""

def validate_description(message):
    result = gemini.beta.chat.completions.parse(
        model="gemini-2.0-flash",
        messages=[{"role": "system", "content": fsd_system_prompt},
                  {"role": "user", "content": message}],
        response_format=StandardSchema
    )
    return result.choices[0].message.parsed

def generate_fsd(structured_summary):
    fsd_prompt = f"""
You are an expert Senior Business Analyst and Technical Writer.
Your task is to convert the structured summary below into a complete
Functional Specifications Document (FSD), filling missing details with:

- [TBD - To Be Discussed] for unknown requirements
- [Assumption - Please Validate] for inferred items

Follow the **STRICT FSD format below**:

# Functional Specifications Document: [Project Name - infer from context]

## 1.0 Introduction
### 1.1 Background
### 1.2 Scope
### 1.3 Out of Scope

## 2.0 Assumptions and Dependencies

## 3.0 Functional Requirements
- Organize by Feature
- For each feature include:
  **Use Case**
  - Use Case ID (FR-x-UC-xx)
  - Process Description
  - Goal
  - Actor(s)
  - System Features
  - Event/Trigger
  - Basic Flow
  - Alternate Flow
  - Pre-Condition
  - Post-Condition
  - Validation / Rules

  **User Story**
  **Acceptance Criteria (testable)**

## 4.0 Non-Functional Requirements (NFRs)
- Security
- Performance
- Usability
- Logging & Monitoring
- Reliability
- Device/Browser Compatibility

Insert [TBD] wherever the provided input lacks clarity.

--------------------------------------
STRUCTURED INPUT SUMMARY
--------------------------------------
{structured_summary}

Now generate the complete FSD.
"""

    fsd_response = gemini.beta.chat.completions.parse(
        model="gemini-2.0-flash",
        messages=[{"role": "user", "content": fsd_prompt}],
        response_format=StandardSchema
    )

    return fsd_response.choices[0].message.parsed.output

# Initialize session state
if 'validated' not in st.session_state:
    st.session_state.validated = False
if 'structured_summary' not in st.session_state:
    st.session_state.structured_summary = None
if 'fsd_generated' not in st.session_state:
    st.session_state.fsd_generated = False
if 'fsd_content' not in st.session_state:
    st.session_state.fsd_content = None

# Header
st.markdown("""
    <div class="header-container">
        <h1>📋 FSD Generator</h1>
        <p style="font-size: 1.2rem; margin-top: 0.5rem;">
            Transform your software descriptions into professional Functional Specifications Documents
        </p>
    </div>
""", unsafe_allow_html=True)

# Step indicator
current_step = 1
if st.session_state.validated:
    current_step = 2
if st.session_state.fsd_generated:
    current_step = 3

st.markdown(f"""
    <div class="step-indicator">
        <div class="step {'step-active' if current_step >= 1 else ''}">1. Describe</div>
        <div class="step {'step-active' if current_step >= 2 else ''}">2. Validate</div>
        <div class="step {'step-active' if current_step >= 3 else ''}">3. Generate</div>
    </div>
""", unsafe_allow_html=True)

# Main content area
if not st.session_state.validated:
    st.markdown("### 📝 Step 1: Describe Your Software")
    st.markdown("Provide a brief description of your software. Don't worry about missing details – we'll handle those later!")
    
    with st.form("description_form"):
        user_input = st.text_area(
            "Software Description",
            height=200,
            placeholder="Example: A web application for managing employee leave requests. Employees can submit leave requests, managers can approve or reject them, and HR can view reports...",
            help="Describe what your software does and what problem it solves"
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submit_button = st.form_submit_button("🔍 Validate Description")
        
        if submit_button:
            if user_input.strip():
                with st.spinner("🤔 Analyzing your description..."):
                    try:
                        validation_result = validate_description(user_input)
                        
                        if validation_result.understood:
                            st.session_state.validated = True
                            st.session_state.structured_summary = validation_result.output
                            st.rerun()
                        else:
                            st.markdown(f"""
                                <div class="warning-box">
                                    <strong>⚠️ Needs Clarification</strong><br>
                                    {validation_result.feedback}
                                </div>
                            """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Please enter a software description.")

elif not st.session_state.fsd_generated:
    st.markdown("### ✅ Step 2: Review Structured Summary")
    
    st.markdown("""
        <div class="success-box">
            <strong>✓ Description Validated Successfully!</strong><br>
            Here's the structured summary we extracted from your description.
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("#### Structured Summary:")
    st.info(st.session_state.structured_summary)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Start Over"):
            st.session_state.validated = False
            st.session_state.structured_summary = None
            st.rerun()
    
    with col3:
        if st.button("Generate FSD →"):
            with st.spinner("🚀 Generating your FSD document..."):
                try:
                    fsd_content = generate_fsd(st.session_state.structured_summary)
                    st.session_state.fsd_content = fsd_content
                    st.session_state.fsd_generated = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error generating FSD: {str(e)}")

else:
    st.markdown("### 📄 Step 3: Your FSD Document")
    
    st.markdown("""
        <div class="success-box">
            <strong>🎉 FSD Generated Successfully!</strong><br>
            Your Functional Specifications Document is ready.
        </div>
    """, unsafe_allow_html=True)
    
    # Display FSD in a nice container
    st.markdown("---")
    st.markdown(st.session_state.fsd_content)
    st.markdown("---")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Generate New FSD"):
            st.session_state.validated = False
            st.session_state.structured_summary = None
            st.session_state.fsd_generated = False
            st.session_state.fsd_content = None
            st.rerun()
    
    with col2:
        st.download_button(
            label="📥 Download as Markdown",
            data=st.session_state.fsd_content,
            file_name="functional_specifications_document.md",
            mime="text/markdown"
        )
    
    with col3:
        if st.button("📋 Copy to Clipboard"):
            st.code(st.session_state.fsd_content, language=None)
            st.success("✓ Displayed above - use your browser's copy function")

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #6c757d; padding: 1rem;">
        <p>💡 <strong>Tips:</strong> Missing information will be marked as [TBD] or [Assumption] for later discussion</p>
    </div>
""", unsafe_allow_html=True)