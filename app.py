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

# Generate AI insight for synthesis lines
@st.cache_data(show_spinner=False)
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

# Function to inject custom CSS
def inject_custom_css():
    custom_css = """
    <style>
    .search-result {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        transition: box-shadow 0.3s;
    }
    .search-result:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    .synthesis {
        font-size: 18px;
        font-weight: bold;
        color: #1a0dab;
    }
    .metadata {
        font-size: 14px;
        color: #6a6a6a;
        margin-top: 8px;
    }
    .view-source {
        margin-top: 12px;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# Main function to run the Streamlit app
def main():
    st.set_page_config(page_title="DevReport Explorer", layout="wide")
    
    # Inject custom CSS
    inject_custom_css()
    
    # Sidebar with the new title
    st.sidebar.title("📚 DevReports Explorer")

    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    org_names = [os.path.splitext(f)[0] for f in csv_files]
    dropdown_options = ["All"] + org_names
    org_to_file = dict(zip(org_names, csv_files))
    
    selected_option = st.sidebar.selectbox("Select Data Source:", options=dropdown_options, index=0)
    topic = st.sidebar.text_input("Enter a topic of interest:", value=st.session_state.get('topic', ''))
    
    if 'current_start' not in st.session_state:
        st.session_state.current_start = 0
    if 'topic' not in st.session_state:
        st.session_state.topic = ''
    
    if st.session_state.topic != topic:
        st.session_state.topic = topic
        st.session_state.current_start = 0

    if selected_option:
        df = load_data(selected_option, org_to_file)
    else:
        st.error("No data source selected.")
        st.stop()
    
    if not topic:
        total_paragraphs = len(df)
        number_of_orgs = df['organization'].nunique()
        st.write(
            f"Explore topics of interest in {total_paragraphs} results across {number_of_orgs} organisations."
        )
        st.info("Please enter a topic of interest to begin your search.")
    else:
        filtered_data = df[df['paragraph'].str.contains(topic, case=False, na=False)]
        if filtered_data.empty:
            st.write("Explore topics of interest in 0 results across 0 organisations.")
            st.warning(f"No paragraphs found for the topic '{topic}'. Please try a different topic.")
            st.stop()
    
        total_paragraphs = len(filtered_data)
        start = st.session_state.current_start
        end = start + 10

        # Show next 10 results
        paginated_data = filtered_data.iloc[start:end]
        
        for idx, row in paginated_data.iterrows():
            paragraph = row['paragraph']
            organization = row.get('organization', 'Organization not available')
            year = row.get('year', 'Year not available')
            country = row.get('country', '').strip()

            # Generate synthesis line and display it in bold
            synthesis = generate_synthesis(paragraph, topic)
            
            # Construct the reference with organization, country (if available), and year
            if country:
                reference = f"{organization} {country}, {year}"
            else:
                reference = f"{organization}, {year}"
            
            # Use HTML to structure the search result
            search_result_html = f"""
            <div class="search-result">
                <div class="synthesis">{synthesis}</div>
                <div class="metadata">{reference}</div>
                <div class="view-source">
                    <button onclick="alert(`{paragraph} ({reference})`)" style="background-color: #f8f9fa; border: 1px solid #dcdcdc; padding: 8px 12px; border-radius: 4px; cursor: pointer;">View Source</button>
                </div>
            </div>
            """
            st.markdown(search_result_html, unsafe_allow_html=True)
        
        # Navigation Buttons
        col1, col2 = st.columns([1, 1])
        
        if col1.button("⬅️ Previous", disabled=start == 0):
            st.session_state.current_start = max(0, start - 10)
            st.experimental_rerun()
        
        if col2.button("Next ➡️", disabled=end >= total_paragraphs):
            st.session_state.current_start = min(total_paragraphs, end)
            st.experimental_rerun()

        # Display progress
        st.write(f"Showing {start + 1} to {min(end, total_paragraphs)} of {total_paragraphs} results.")

if __name__ == "__main__":
    main()
