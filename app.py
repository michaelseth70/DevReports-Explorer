# streamlit-app.py

import streamlit as st
import pandas as pd
import os
import openai
from functools import lru_cache

# --------------------------
# Configuration and Setup
# --------------------------

# Set the page configuration
st.set_page_config(
    page_title="DevReports Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize OpenAI API using Streamlit secrets
openai.api_key = st.secrets["openai"]["api_key"]

# Constants
RESULTS_PER_PAGE = 10

# --------------------------
# Caching Functions
# --------------------------

@st.cache_data
def load_data(selected_option, org_to_file):
    if selected_option == "All":
        data_frames = []
        for org, file in org_to_file.items():
            try:
                df = pd.read_csv(file)
                df['organization'] = org
                data_frames.append(df)
            except Exception as e:
                st.error(f"Error loading {file}: {e}")
        if data_frames:
            combined_df = pd.concat(data_frames, ignore_index=True)
            required_columns = {'paragraph'}
            if not required_columns.issubset(combined_df.columns):
                st.error(f"One or more CSV files are missing required columns: {required_columns}")
                st.stop()
            return combined_df
        else:
            st.error("No CSV files found in the directory.")
            st.stop()
    else:
        file = org_to_file[selected_option]
        try:
            df = pd.read_csv(file)
            df['organization'] = selected_option
            required_columns = {'paragraph'}
            if not required_columns.issubset(df.columns):
                st.error(f"The selected CSV file must contain the following columns: {required_columns}")
                st.stop()
            return df
        except FileNotFoundError:
            st.error(f"The file '{file}' was not found.")
            st.stop()
        except Exception as e:
            st.error(f"An error occurred while loading the data: {e}")
            st.stop()

@st.cache_data(show_spinner=False, ttl=3600)
def generate_synthesis(paragraph, topic):
    prompt = (
        f"Provide a plain text one-line insightful summary for someone interested in '{topic}' based on the following paragraph:\n\n"
        f"{paragraph}\n\nSynthesis:"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an insightful analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        synthesis = response.choices[0].message['content'].strip()
    except Exception as e:
        synthesis = "Synthesis generation failed."
        st.error(f"Error generating synthesis: {e}")
    return synthesis

# --------------------------
# Helper Functions
# --------------------------

def get_org_files(data_dir='data'):
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    org_names = [os.path.splitext(f)[0] for f in csv_files]
    org_to_file = dict(zip(org_names, csv_files))
    return org_names, org_to_file

# --------------------------
# Main Application
# --------------------------

def main():
    # Inject custom CSS
    # Streamlit automatically includes CSS from the assets folder
    # Ensure that 'style.css' is placed inside the 'assets' folder

    # Sidebar Configuration
    with st.sidebar:
        st.title("📚 DevReports Explorer")
        org_names, org_to_file = get_org_files()
        dropdown_options = ["All"] + org_names
        selected_option = st.selectbox("Select Data Source:", options=dropdown_options, index=0)
        topic = st.text_input("Enter a topic of interest:", value=st.session_state.get('topic', ''))

        if 'current_start' not in st.session_state:
            st.session_state.current_start = 0
        if 'topic' not in st.session_state:
            st.session_state.topic = ''

        if st.session_state.topic != topic:
            st.session_state.topic = topic
            st.session_state.current_start = 0

    # Main Content
    st.markdown("<h1 style='text-align: center; color: #1a0dab;'>DevReports Explorer</h1>", unsafe_allow_html=True)
    
    if selected_option:
        df = load_data(selected_option, org_to_file)
    else:
        st.error("No data source selected.")
        st.stop()

    if not topic:
        total_paragraphs = len(df)
        number_of_orgs = df['organization'].nunique()
        st.markdown(
            f"<p style='text-align: center;'>Explore topics of interest in <strong>{total_paragraphs}</strong> results across <strong>{number_of_orgs}</strong> organisations.</p>",
            unsafe_allow_html=True
        )
        st.info("Please enter a topic of interest to begin your search.")
    else:
        filtered_data = df[df['paragraph'].str.contains(topic, case=False, na=False)]
        if filtered_data.empty:
            st.markdown("<h3 style='text-align: center;'>No Results Found</h3>", unsafe_allow_html=True)
            st.warning(f"No paragraphs found for the topic '{topic}'. Please try a different topic.")
            st.stop()

        total_paragraphs = len(filtered_data)
        total_pages = (total_paragraphs - 1) // RESULTS_PER_PAGE + 1

        start = st.session_state.current_start
        end = start + RESULTS_PER_PAGE

        paginated_data = filtered_data.iloc[start:end]

        # Display Search Results
        for idx, row in paginated_data.iterrows():
            paragraph = row['paragraph']
            organization = row.get('organization', 'Organization not available')
            year = row.get('year', 'Year not available')
            country = row.get('country', '').strip()

            # Generate synthesis line
            synthesis = generate_synthesis(paragraph, topic)

            # Construct reference
            if country:
                reference = f"{organization} {country}, {year}"
            else:
                reference = f"{organization}, {year}"

            # Render Search Result Card
            with st.container():
                st.markdown(
                    f"""
                    <div class="search-result">
                        <div class="synthesis">{synthesis}</div>
                        <div class="metadata">{reference}</div>
                        <button class="view-source-button" onclick="document.getElementById('source-{idx}').classList.toggle('hidden')">View Source</button>
                        <div id="source-{idx}" class="hidden" style="margin-top: 10px;">
                            <p>{paragraph} ({reference})</p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Pagination Controls
        pagination_container = st.container()
        with pagination_container:
            cols = st.columns([1, 2, 1])
            with cols[0]:
                if st.button("⬅️ Previous"):
                    st.session_state.current_start = max(0, start - RESULTS_PER_PAGE)
                    st.experimental_rerun()
            with cols[1]:
                st.markdown(f"<p style='text-align: center;'>Page {start // RESULTS_PER_PAGE + 1} of {total_pages}</p>", unsafe_allow_html=True)
            with cols[2]:
                if st.button("Next ➡️"):
                    st.session_state.current_start = min(start + RESULTS_PER_PAGE, total_paragraphs - RESULTS_PER_PAGE)
                    st.experimental_rerun()

            st.markdown(f"<p style='text-align: center;'>Showing {start + 1} to {min(end, total_paragraphs)} of {total_paragraphs} results.</p>", unsafe_allow_html=True)

# --------------------------
# Run the Application
# --------------------------

if __name__ == "__main__":
    main()
