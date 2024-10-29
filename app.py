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

# Main function to run the Streamlit app
def main():
    st.set_page_config(page_title="DevReport Explorer", layout="wide")
    
    st.title("📚 DevReports Explorer")
    heading_placeholder = st.empty()
    st.sidebar.title("🔍 Explore Reports")

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
        heading_placeholder.write(
            f"Explore topics of interest in {total_paragraphs} results across {number_of_orgs} organisations."
        )
        st.info("Please enter a topic of interest to begin your search.")
    else:
        filtered_data = df[df['paragraph'].str.contains(topic, case=False, na=False)]
        if filtered_data.empty:
            heading_placeholder.write("Explore topics of interest in 0 results across 0 organisations.")
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

            # Generate synthesis line
            synthesis = generate_synthesis(paragraph, topic)
            st.write(f"**Insight**: {synthesis}")

            # Button to view full source
            if st.button(f"View Source ({organization}, {year})", key=f"view_source_{idx}"):
                st.write(f"{paragraph} ({organization}, {year})")
        
        # Navigation Buttons
        col1, col2 = st.columns([1, 1])
        
        if col1.button("⬅️ Previous", disabled=start == 0):
            st.session_state.current_start = max(0, start - 10)
        
        if col2.button("Next ➡️", disabled=end >= total_paragraphs):
            st.session_state.current_start = min(total_paragraphs, end)

        # Display progress
        st.write(f"Showing {start + 1} to {min(end, total_paragraphs)} of {total_paragraphs}")

if __name__ == "__main__":
    main()
