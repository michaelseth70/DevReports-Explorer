# app.py

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import os
import openai
import math
from functools import lru_cache
import urllib.parse

# Initialize OpenAI API using environment variable or other secure methods
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # For deploying to platforms like Heroku

# Constants
RESULTS_PER_PAGE = 10

# Caching loaded data
@lru_cache(maxsize=32)
def load_data(selected_option, org_to_file):
    if selected_option == "All":
        data_frames = []
        for org, file in org_to_file:
            try:
                df = pd.read_csv(file)
                df['organization'] = org
                data_frames.append(df)
            except Exception as e:
                # Logging can be added here
                print(f"Error loading {file}: {e}")
        if data_frames:
            combined_df = pd.concat(data_frames, ignore_index=True)
            required_columns = {'paragraph'}
            if not required_columns.issubset(combined_df.columns):
                raise ValueError(f"One or more CSV files are missing required columns: {required_columns}")
            return combined_df
        else:
            raise FileNotFoundError("No CSV files found in the directory.")
    else:
        file = org_to_file[selected_option]
        try:
            df = pd.read_csv(file)
            df['organization'] = selected_option
            required_columns = {'paragraph'}
            if not required_columns.issubset(df.columns):
                raise ValueError(f"The selected CSV file must contain the following columns: {required_columns}")
            return df
        except FileNotFoundError:
            raise FileNotFoundError(f"The file '{file}' was not found.")
        except Exception as e:
            raise e

# Caching synthesis results
@lru_cache(maxsize=1000)
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
        print(f"Error generating synthesis: {e}")
    return synthesis

# Helper function to retrieve CSV files and organizations
def get_org_files():
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    org_names = [os.path.splitext(f)[0] for f in csv_files]
    org_to_file = dict(zip(org_names, csv_files))
    return org_names, org_to_file

# Layout Components

# Sidebar Layout
sidebar = dbc.Card(
    [
        dbc.CardHeader(html.H4("📚 DevReports Explorer")),
        dbc.CardBody(
            [
                html.Label("Select Data Source:", className="fw-bold"),
                dcc.Dropdown(
                    id='data-source-dropdown',
                    options=[],
                    value="All",
                    clearable=False
                ),
                html.Br(),
                html.Label("Enter a topic of interest:", className="fw-bold"),
                dcc.Input(
                    id='topic-input',
                    type='text',
                    placeholder='e.g., Artificial Intelligence',
                    debounce=True,
                    style={"width": "100%"}
                ),
                html.Br(),
                html.Br(),
                dbc.Button(
                    "Search",
                    id='search-button',
                    color="primary",
                    className="w-100"  # Makes the button full-width
                ),
            ]
        ),
    ],
    style={"position": "fixed", "width": "20rem", "height": "100vh", "overflow": "auto"},
)

# Search Result Card Component
def create_search_card(synthesis, reference, paragraph, idx):
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(synthesis, className="synthesis"),
                html.P(reference, className="metadata"),
                dbc.Collapse(
                    dbc.Card(
                        dbc.CardBody(paragraph)
                    ),
                    id={'type': 'collapse', 'index': idx},
                    is_open=False,
                ),
                dbc.Button(
                    "View Source",
                    id={'type': 'toggle', 'index': idx},
                    color="link",
                    n_clicks=0,
                )
            ]
        ),
        className="search-result mb-3",
    )

# Main Content Layout
content = dbc.Container(
    [
        html.Div(id='search-results'),
        html.Br(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button("⬅️ Previous", id='prev-button', color="secondary", disabled=True),
                    width="auto"
                ),
                dbc.Col(
                    dbc.Button("Next ➡️", id='next-button', color="secondary", disabled=True),
                    width="auto"
                ),
            ],
            justify="center",
            align="center",
        ),
        html.Br(),
        html.Div(id='pagination-info', style={"textAlign": "center"}),
    ],
    style={"marginLeft": "22rem", "padding": "2rem 1rem"}
)

# Complete Layout
app.layout = html.Div([
    dcc.Store(id='current-page', data=1),
    sidebar,
    content,
    # Custom CSS for styling
    html.Style("""
        .synthesis {
            color: #1a0dab;
            font-size: 1.25rem;
            font-weight: bold;
            cursor: pointer;
        }
        .metadata {
            color: #6a6a6a;
            font-size: 0.9rem;
        }
        .search-result {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            transition: box-shadow 0.3s;
        }
        .search-result:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
    """)
])

# Callbacks

# Initialize Dropdown Options on Page Load
@app.callback(
    Output('data-source-dropdown', 'options'),
    Output('data-source-dropdown', 'value'),
    Input('data-source-dropdown', 'id')  # Dummy input to trigger on load
)
def update_dropdown_options(_):
    org_names, _ = get_org_files()
    options = [{'label': org, 'value': org} for org in org_names]
    options.insert(0, {'label': 'All', 'value': 'All'})
    return options, 'All'

# Handle Search Button Click
@app.callback(
    Output('search-results', 'children'),
    Output('pagination-info', 'children'),
    Output('prev-button', 'disabled'),
    Output('next-button', 'disabled'),
    Output('current-page', 'data'),
    Input('search-button', 'n_clicks'),
    State('data-source-dropdown', 'value'),
    State('topic-input', 'value'),
    State('current-page', 'data')
)
def perform_search(n_clicks, selected_option, topic, current_page):
    if not n_clicks:
        return [], "", True, True, 1
    if not topic:
        return [], dbc.Alert("Please enter a topic of interest to begin your search.", color="info"), True, True, 1
    org_names, org_to_file = get_org_files()
    try:
        df = load_data(selected_option, tuple(org_to_file.items()))
    except Exception as e:
        return [], dbc.Alert(str(e), color="danger"), True, True, 1
    filtered_df = df[df['paragraph'].str.contains(topic, case=False, na=False)]
    if filtered_df.empty:
        return [], dbc.Alert(f"No paragraphs found for the topic '{topic}'. Please try a different topic.", color="warning"), True, True, 1
    total_paragraphs = len(filtered_df)
    total_pages = math.ceil(total_paragraphs / RESULTS_PER_PAGE)
    # Adjust current_page if out of range
    current_page = min(max(1, current_page), total_pages)
    start = (current_page - 1) * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    paginated_data = filtered_df.iloc[start:end].reset_index(drop=True)
    search_cards = []
    for idx, row in paginated_data.iterrows():
        paragraph = row['paragraph']
        organization = row.get('organization', 'Organization not available')
        year = row.get('year', 'Year not available')
        country = row.get('country', '').strip()
        if country:
            reference = f"{organization} {country}, {year}"
        else:
            reference = f"{organization}, {year}"
        synthesis = generate_synthesis(paragraph, topic)
        card = create_search_card(synthesis, reference, paragraph, idx + (current_page -1 ) * RESULTS_PER_PAGE)
        search_cards.append(card)
    # Determine button states
    prev_disabled = current_page == 1
    next_disabled = current_page >= total_pages
    # Pagination info
    info = f"Showing {start + 1} to {min(end, total_paragraphs)} of {total_paragraphs} results."
    return search_cards, info, prev_disabled, next_disabled, current_page

# Handle Pagination Buttons
@app.callback(
    Output('current-page', 'data'),
    Output('search-button', 'n_clicks'),
    Input('prev-button', 'n_clicks'),
    Input('next-button', 'n_clicks'),
    State('current-page', 'data'),
    prevent_initial_call=True
)
def update_page(prev_clicks, next_clicks, current_page):
    ctx = callback_context
    if not ctx.triggered:
        return current_page, dash.no_update
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    org_names, org_to_file = get_org_files()
    # Assuming 'n_clicks' for search is preserved elsewhere
    if button_id == 'prev-button' and current_page > 1:
        return current_page - 1, 0
    elif button_id == 'next-button':
        return current_page + 1, 0
    return current_page, dash.no_update

# Toggle Collapse for View Source
@app.callback(
    Output({'type': 'collapse', 'index': dash.MATCH}, 'is_open'),
    Input({'type': 'toggle', 'index': dash.MATCH}, 'n_clicks'),
    State({'type': 'collapse', 'index': dash.MATCH}, 'is_open'),
)
def toggle_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

# Run the Dash app
if __name__ == '__main__':
    app.run_server(debug=True)
