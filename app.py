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
    """
    Load data based on the selected option.
    If 'All' is selected, load and concatenate all CSVs.
    Otherwise, load the specific CSV corresponding to the selected organization.
    Adds an 'organization' column based on the organization name.
    """
    if selected_option == "All":
        data_frames = []
        for org, file in org_to_file.items():
            try:
                df = pd.read_csv(file)
                df['organization'] = org  # Add organization name
                data_frames.append(df)
            except Exception as e:
                st.error(f"Error loading {file}: {e}")
        if data_frames:
            combined_df = pd.concat(data_frames, ignore_index=True)
            # Validate required columns
            required_columns = {'paragraph'}
            if not required_columns.issubset(combined_df.columns):
                st.error(f"One or more CSV files are missing required columns: {required_columns}")
                st.stop()
            return combined_df
        else:
            st.error("No CSV files found in the directory.")
            st.stop()
    else:
        # Load specific organization's CSV
        file = org_to_file[selected_option]
        try:
            df = pd.read_csv(file)
            df['organization'] = selected_option  # Add organization name
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

# Function to filter data based on the topic
def filter_data(df, topic):
    return df[df['paragraph'].str.contains(topic, case=False, na=False)]

# Function to generate AI insights using OpenAI API with caching
@st.cache_data(show_spinner=False)
def generate_insight(paragraph, topic):
    """
    Generates an AI insight for a given paragraph and topic using OpenAI API.
    Caches the result to optimize performance and reduce API calls.
    """
    prompt = (
        f"Provide a plain text insigthful synthesis title in Sentence case related to '{topic}' based on the following paragraph:\n\n"
        f"{paragraph}\n\nInsight:"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # You can choose a different model if preferred
            messages=[
                {"role": "system", "content": "You are an insightful analysis assistant."},
                {"role": "user", "content": prompt}
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
    st.set_page_config(page_title="DevReport Explorer", layout="wide")  # Updated app name
    
    # Add an emoji before the title
    st.title("📚 DevReports Explorer")  # 📄 represents a document/report
    
    # Create a placeholder for dynamic instructional text
    heading_placeholder = st.empty()
    
    # Sidebar: Data selection and topic input
    st.sidebar.title("🔍 Explore Reports")  # Updated sidebar header
    
    # List all CSV files in the current directory and create organization names
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    org_names = [os.path.splitext(f)[0] for f in csv_files]
    dropdown_options = ["All"] + org_names
    
    # Create a mapping from organization name to filename
    org_to_file = dict(zip(org_names, csv_files))
    
    # Dropdown for selecting data source
    selected_option = st.sidebar.selectbox("Select Data Source:", options=dropdown_options, index=0)
    
    # Input field for topic of interest
    topic = st.sidebar.text_input("Enter a topic of interest:", value=st.session_state.get('topic', ''))
    
    # Initialize session state variables if not present
    if 'current_paragraph' not in st.session_state:
        st.session_state.current_paragraph = 0
    if 'topic' not in st.session_state:
        st.session_state.topic = ''
    if 'total_paragraphs' not in st.session_state:
        st.session_state.total_paragraphs = 0
    
    # Update session state for 'topic' and reset paragraph index if topic changes
    if st.session_state.topic != topic:
        st.session_state.topic = topic
        st.session_state.current_paragraph = 0  # Reset paragraph index on topic change
    
    # Load the CSV data based on selection
    if selected_option:
        df = load_data(selected_option, org_to_file)
    else:
        st.error("No data source selected.")
        st.stop()
    
    # When no topic is entered
    if not topic:
        # Display total counts based on selected data source
        total_paragraphs = len(df)
        number_of_orgs = df['organization'].nunique()
        heading_placeholder.write(
            f"Explore topics of interest in {total_paragraphs} results across {number_of_orgs} organisations."
        )
        st.info("Please enter a topic of interest to begin your search.")
    else:
        # Filter the data based on the topic
        filtered_data = filter_data(df, topic)
    
        if filtered_data.empty:
            heading_placeholder.write("Explore topics of interest in 0 results across 0 organisations.")
            st.warning(f"No paragraphs found for the topic '{topic}'. Please try a different topic.")
            st.stop()
    
        total_paragraphs = len(filtered_data)
        st.session_state.total_paragraphs = total_paragraphs  # Store total paragraphs in session state
    
        # Calculate number of unique organisations in the filtered data
        number_of_orgs = filtered_data['organization'].nunique()
    
        # Update the instructional text with dynamic counts and dynamic heading
        heading_placeholder.write(
            f"Showing results for **'{topic}'** in {total_paragraphs} results across {number_of_orgs} organisations."
        )
    
        # Handle Navigation Buttons First
        col1, col2 = st.columns([1, 1])
    
        # Previous Button
        previous_clicked = col1.button("⬅️ Previous")
        # Next Button
        next_clicked = col2.button("Next ➡️")
    
        # Update the 'current_paragraph' based on button clicks
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
    
        # Get the current paragraph data
        paragraph_data = filtered_data.iloc[current_index]
    
        # Extract necessary fields
        paragraph = paragraph_data['paragraph']
        year = paragraph_data.get('year', 'Year not available')
        organization = paragraph_data.get('organization', 'Organization not available')
        country = paragraph_data.get('country', '').strip()
    
        # Construct the reference
        if country:
            reference = f"({organization} {country}, {year})"
        else:
            reference = f"({organization}, {year})"
    
        # Display the "x of x" as regular text
        st.write(f"**{current_index + 1} of {total_paragraphs}**")
    
        # Generate and display the AI-generated insight
        with st.spinner("Generating insight..."):
            insight = generate_insight(paragraph, topic)
        st.markdown(f"**{insight}**")  # Display insight as bold text
    
        # Display the paragraph
        st.write(f"{paragraph} {reference}")
    
        # Progress Bar
        progress = (current_index + 1) / total_paragraphs
        st.progress(progress)
    
if __name__ == "__main__":
    main()
