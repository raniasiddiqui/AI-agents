import os
import re
import json
from datetime import datetime
import streamlit as st
import google.generativeai as genai

# Configure the page
st.set_page_config(
    page_title="Healthcare Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'report_generated' not in st.session_state:
    st.session_state.report_generated = False

# Sidebar for API key configuration
st.sidebar.title("⚙️ Configuration")
api_key = st.sidebar.text_input("Enter Google API Key:", type="password", 
                                value=st.session_state.get('api_key', ''))

if api_key:
    st.session_state.api_key = api_key
    os.environ["GOOGLE_API_KEY"] = api_key
    genai.configure(api_key=api_key)
    st.sidebar.success("✅ API Key configured!")
else:
    st.sidebar.warning("⚠️ Please enter your Google API Key to use the assistant")

MODEL = "gemini-2.0-flash"

# Title and Disclaimer
st.title("🏥 Healthcare Assistant")
st.markdown("---")

st.error("""
**IMPORTANT DISCLAIMER:** This Healthcare Assistant is for educational and informational purposes only. 
It is not a substitute for professional medical advice, diagnosis, or treatment. 
Always consult a qualified healthcare provider for any medical concerns.
""")

class SymptomAnalyzerAgent:
    def __init__(self):
        self.role = "Symptom Analyzer"
        self.backstory = (
            "I am Dr. Insight, a meticulous and empathetic AI trained to analyze patient symptom descriptions. "
            "My goal is to identify patterns in symptoms and suggest possible conditions, always emphasizing caution "
            "and the need for professional medical evaluation. I use structured parsing to ensure clarity."
        )
        self.tools = ["Symptom Parsing Regex", "LLM-based Analysis"]

    def parse_symptoms(self, description, symptom_keywords):
        symptom_patterns = [r'\b(' + re.escape(keyword.lower()) + r')\b' for keyword in symptom_keywords]
        symptoms = []
        for pattern in symptom_patterns:
            matches = re.findall(pattern, description.lower())
            symptoms.extend(matches)
        return list(set(symptoms))

    def analyze(self, description, symptom_keywords):
        symptoms = self.parse_symptoms(description, symptom_keywords)
        system_prompt = (
            f"You are {self.role}, {self.backstory}. Based on the patient's symptom description and parsed symptoms, "
            "suggest 3-5 possible medical conditions in a numbered list. Be cautious, factual, and emphasize that "
            "this is not a diagnosis. Use simple language."
        )
        user_prompt = f"Patient description: {description}\nParsed symptoms: {', '.join(symptoms)}"

        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([system_prompt, user_prompt])

        return {"analysis": response.text.strip(), "symptoms": symptoms}


class MedicalKnowledgeAgent:
    def __init__(self):
        self.role = "Medical Knowledge Retriever"
        self.backstory = (
            "I am Dr. Scholar, an AI with a deep commitment to evidence-based medicine. My purpose is to retrieve and "
            "summarize medical guidelines from trusted, open-source websites like WHO, Mayo Clinic, CDC, and NIH. "
            "I ensure all information is credible and clearly cited."
        )
        self.tools = ["Web Content Summarization", "Source Validation"]
        self.trusted_sources = [
            "who.int", "mayoclinic.org", "cdc.gov", "nih.gov",
            "webmd.com", "medlineplus.gov", "healthline.com",
            "clevelandclinic.org", "nhs.uk"
        ]

    def retrieve_guidelines(self, condition):
        system_prompt = (
            f"You are {self.role}, {self.backstory}. Retrieve and summarize medical guidelines for the given condition "
            f"from trusted sources: {', '.join(self.trusted_sources)}. Provide a concise summary with citations. "
            "If no specific guidelines are found, note this and provide general advice, while emphasizing consulting a healthcare provider."
        )
        user_prompt = f"Condition: {condition}"

        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([system_prompt, user_prompt])

        return response.text.strip()


class LifestyleCoachAgent:
    def __init__(self):
        self.role = "Lifestyle Coach"
        self.backstory = (
            "I am Coach Wellness, an encouraging and practical AI focused on promoting healthy living. I provide "
            "evidence-based diet, exercise, and wellness recommendations tailored to medical conditions, always "
            "urging consultation with a doctor before making changes."
        )
        self.tools = ["Lifestyle Recommendation Generator"]

    def recommend(self, conditions, symptoms):
        system_prompt = (
            f"You are {self.role}, {self.backstory}. Based on the possible medical conditions and symptoms, "
            "provide practical, evidence-based recommendations for diet, exercise, and wellness. "
            "Keep it non-prescriptive and suggest consulting a doctor."
        )
        user_prompt = f"Conditions: {', '.join(conditions)}\nSymptoms: {', '.join(symptoms)}"

        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([system_prompt, user_prompt])

        return response.text.strip()


class ReportGeneratorAgent:
    def __init__(self):
        self.role = "Report Generator"
        self.backstory = (
            "I am Dr. Summary, a precise and professional AI designed to compile clear, structured reports for doctors. "
            "I synthesize patient data, symptom analysis, medical guidelines, and lifestyle advice into concise summaries."
        )
        self.tools = ["Structured Report Template"]

    def generate_report(self, description, analysis_data, knowledge_data, lifestyle):
        system_prompt = (
            f"You are {self.role}, {self.backstory}. Compile a professional summary report for a doctor, including "
            "patient description, symptom analysis, medical knowledge, and lifestyle recommendations."
            "Use clear sections and a professional tone."
        )
        user_prompt = (
            f"Patient Description: {description}\n\n"
            f"Symptom Analysis: {analysis_data['analysis']}\nParsed Symptoms: {', '.join(analysis_data['symptoms'])}\n\n"
            f"Medical Knowledge: {json.dumps(knowledge_data, indent=2)}\n\n"
            f"Lifestyle Recommendations: {lifestyle}"
        )

        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([system_prompt, user_prompt])

        return response.text.strip()


class HealthcareAssistant:
    def __init__(self):
        self.symptom_analyzer = SymptomAnalyzerAgent()
        self.medical_knowledge = MedicalKnowledgeAgent()
        self.lifestyle_coach = LifestyleCoachAgent()
        self.report_generator = ReportGeneratorAgent()

    def run(self, patient_description, symptom_keywords):
        # Store results in session state for persistence
        results = {}
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Symptom Analysis
        status_text.text("🔍 Dr. Insight is analyzing symptoms...")
        progress_bar.progress(20)
        
        analysis_data = self.symptom_analyzer.analyze(patient_description, symptom_keywords)
        results['analysis_data'] = analysis_data
        
        # Extract conditions from analysis
        conditions = []
        for line in analysis_data['analysis'].split('\n'):
            if line.strip().startswith(('1.', '2.', '3.', '4.', '5.')):
                condition = line.strip()[2:].strip()
                if condition:
                    conditions.append(condition)
        if not conditions:
            conditions = [analysis_data['analysis'].split('\n')[0]]
        
        results['conditions'] = conditions
        progress_bar.progress(40)
        
        # Step 2: Medical Knowledge Retrieval
        status_text.text("📚 Dr. Scholar is retrieving medical guidelines...")
        knowledge_data = {}
        for i, condition in enumerate(conditions):
            knowledge_data[condition] = self.medical_knowledge.retrieve_guidelines(condition)
            progress_bar.progress(40 + (30 // len(conditions)) * (i + 1))
        
        results['knowledge_data'] = knowledge_data
        
        # Step 3: Lifestyle Recommendations
        status_text.text("💪 Coach Wellness is generating lifestyle recommendations...")
        progress_bar.progress(80)
        
        lifestyle = self.lifestyle_coach.recommend(conditions, analysis_data['symptoms'])
        results['lifestyle'] = lifestyle
        
        # Step 4: Report Generation
        status_text.text("📋 Dr. Summary is compiling the final report...")
        progress_bar.progress(90)
        
        report = self.report_generator.generate_report(patient_description, analysis_data, knowledge_data, lifestyle)
        results['report'] = report
        
        progress_bar.progress(100)
        status_text.text("✅ Analysis complete!")
        
        return results


# Main Interface
st.markdown("## 📝 Patient Information")

# Input fields
col1, col2 = st.columns([2, 1])

with col1:
    patient_desc = st.text_area(
        "Describe your symptoms:",
        placeholder="e.g., 'I have a persistent cough and fever for 3 days'",
        height=100
    )

with col2:
    symptom_keywords = st.text_input(
        "Symptom keywords (comma-separated):",
        placeholder="e.g., cough, fever, headache"
    )
    
    # Convert keywords to list
    if symptom_keywords:
        keyword_list = [keyword.strip() for keyword in symptom_keywords.split(',')]
    else:
        keyword_list = []

# Analyze button
analyze_button = st.button("🔍 Analyze Symptoms", type="primary", disabled=not api_key)

if not api_key:
    st.warning("Please enter your Google API Key in the sidebar to proceed.")

# Main analysis execution
if analyze_button and patient_desc and keyword_list and api_key:
    try:
        assistant = HealthcareAssistant()
        
        # Run analysis
        with st.spinner("Analyzing..."):
            results = assistant.run(patient_desc, keyword_list)
        
        st.session_state.results = results
        st.session_state.report_generated = True
        st.success("Analysis completed successfully!")
        
    except Exception as e:
        st.error(f"An error occurred during analysis: {str(e)}")

# Display results if available
if st.session_state.report_generated and 'results' in st.session_state:
    results = st.session_state.results
    
    st.markdown("---")
    st.markdown("## 📊 Analysis Results")
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Symptom Analysis", 
        "📚 Medical Guidelines", 
        "💪 Lifestyle Recommendations", 
        "📋 Doctor Report"
    ])
    
    with tab1:
        st.markdown("### Dr. Insight's Analysis")
        st.write(results['analysis_data']['analysis'])
        
        if results['analysis_data']['symptoms']:
            st.markdown("**Parsed Symptoms:**")
            for symptom in results['analysis_data']['symptoms']:
                st.markdown(f"• {symptom.capitalize()}")
    
    with tab2:
        st.markdown("### Dr. Scholar's Medical Guidelines")
        for condition, guideline in results['knowledge_data'].items():
            with st.expander(f"📖 {condition}"):
                st.write(guideline)
    
    with tab3:
        st.markdown("### Coach Wellness's Recommendations")
        st.write(results['lifestyle'])
    
    with tab4:
        st.markdown("### Dr. Summary's Professional Report")
        st.write(results['report'])
        
        # Download button for the report
        report_filename = f"healthcare_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(
            label="📥 Download Report",
            data=results['report'],
            file_name=report_filename,
            mime="text/plain"
        )

# Sidebar information
st.sidebar.markdown("---")
st.sidebar.markdown("### 👥 AI Agents")
st.sidebar.markdown("""
- **🔍 Dr. Insight**: Symptom Analyzer
- **📚 Dr. Scholar**: Medical Knowledge Retriever  
- **💪 Coach Wellness**: Lifestyle Coach
- **📋 Dr. Summary**: Report Generator
""")

st.sidebar.markdown("### 🔗 Trusted Medical Sources")
st.sidebar.markdown("""
- WHO (who.int)
- Mayo Clinic (mayoclinic.org)
- CDC (cdc.gov)
- NIH (nih.gov)
- WebMD (webmd.com)
- MedlinePlus (medlineplus.gov)
- Healthline (healthline.com)
- Cleveland Clinic (clevelandclinic.org)
- NHS (nhs.uk)
""")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Healthcare Assistant v1.0 | For educational purposes only | Always consult a healthcare professional"
    "</div>", 
    unsafe_allow_html=True
)