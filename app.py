import streamlit as st
import pandas as pd
import os
import openai
from functools import lru_cache

# Initialize OpenAI API using Streamlit secrets
openai.api_key = st.secrets["openai"]["api_key"]

# Load the CSV files with caching
@st.cache_data
def load_data(selected_option, org_to_file):
    # ... [Your existing load_data function code] ...

# Function to filter data based on the topic
def filter_data(df, topic):
    return df[df['paragraph'].str.contains(topic, case=False, na=False)]

# Updated generate_insight function using ChatCompletion
def generate_insight(paragraph, topic):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Use "gpt-4" if available
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Provide a concise and insightful analysis related to the topic '{topic}' based on the following paragraph:\n\n{paragraph}"}
            ],
            max_tokens=100,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        insight = response.choices[0].message['content'].strip()
    except Exception as e:
        insight = "Insight generation failed."
        st.error(f"Error generating insight: {e}")
    return insight

# Main function to run the Streamlit app
def main():
    st.set_page_config(page_title="DevReport Explorer", layout="wide")
    st.title("📚 DevReports Explorer")
    heading_placeholder = st.empty()
    st.sidebar.title("🔍 Explore Reports")
    
    # List all CSV files and create organization names
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    org_names = [os.path.splitext(f)[0] for f in csv_files]
    dropdown_options = ["All"] + org_names
    org_to_file = dict(zip(org_names, csv_files))
    selected_option = st.sidebar.selectbox("Select Data Source:", options=dropdown_options, index=0)
    topic = st.sidebar.text_input("Enter a topic of interest:", value=st.session_state.get('topic', ''))
    
    # Initialize session state variables
    if 'current_paragraph' not in st.session_state:
        st.session_state.current_paragraph = 0
    if 'topic' not in st.session_state:
        st.session_state.topic = ''
    if 'total_paragraphs' not in st.session_state:
        st.session_state.total_paragraphs = 0
    
    # Update session state for 'topic' and reset paragraph index if topic changes
    if st.session_state.topic != topic:
        st.session_state.topic = topic
        st.session_state.current_paragraph = 0
    
    # Load the CSV data based on selection
    if selected_option:
        df = load_data(selected_option, org_to_file)
    else:
        st.error("No data source selected.")
        st.stop()
    
    # When no topic is entered
    if not topic:
        total_paragraphs = len(df)
        number_of_orgs = df['organization'].nunique()
        heading_placeholder.write(f"Explore topics of interest in {total_paragraphs} results across {number_of_orgs} organisations.")
        st.info("Please enter a topic of interest to begin your search.")
    else:
        # Filter the data based on the topic
        filtered_data = filter_data(df, topic)
        if filtered_data.empty:
            heading_placeholder.write("Explore topics of interest in 0 results across 0 organisations.")
            st.warning(f"No paragraphs found for the topic '{topic}'. Please try a different topic.")
            st.stop()
        
        total_paragraphs = len(filtered_data)
        st.session_state.total_paragraphs = total_paragraphs
        number_of_orgs = filtered_data['organization'].nunique()
        heading_placeholder.write(f"Showing results for **'{topic}'** in {total_paragraphs} results across {number_of_orgs} organisations.")
        
        # Handle Navigation Buttons
        col1, col2 = st.columns([1, 1])
        previous_clicked = col1.button("⬅️ Previous")
        next_clicked = col2.button("Next ➡️")
        
        if previous_clicked:
            if st.session_state.current_paragraph > 0:
                st.session_state.current_paragraph -= 1
        if next_clicked:
            if st.session_state.current_paragraph < total_paragraphs - 1:
                st.session_state.current_paragraph += 1
        
        # Ensure 'current_paragraph' is within bounds
        if st.session_state.current_paragraph >= total_paragraphs:
            st.session_state.current_paragraph = total_paragraphs - 1
        if st.session_state.current_paragraph < 0:
            st.session_state.current_paragraph = 0
        
        current_index = st.session_state.current_paragraph
        paragraph_data = filtered_data.iloc[current_index]
        paragraph = paragraph_data['paragraph']
        year = paragraph_data.get('year', 'Year not available')
        organization = paragraph_data.get('organization', 'Organization not available')
        country = paragraph_data.get('country', '').strip()
        
        if country:
            reference = f"({organization} {country}, {year})"
        else:
            reference = f"({organization}, {year})"
        
        st.write(f"**{current_index + 1} of {total_paragraphs}**")
        
        # Generate and display the AI-generated insight
        with st.spinner("Generating insight..."):
            insight = generate_insight(paragraph, topic)
        st.markdown(f"**{insight}**")  # Display insight as bold text
        st.write(f"{paragraph} {reference}")
        
        # Progress Bar
        progress = (current_index + 1) / total_paragraphs
        st.progress(progress)

if __name__ == "__main__":
    main()
