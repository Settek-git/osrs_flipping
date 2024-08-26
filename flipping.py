import streamlit as st
import requests
import pandas as pd
import os
from random import randint
from math import floor

# Set the page configuration to use the wide layout
st.set_page_config(layout="wide")

# Hardcoded username and password for simplicity
VALID_USERNAME = os.getenv("USERNAME") 
VALID_PASSWORD = os.getenv("PASSWORD") 

# File to store analysis history
HISTORY_FILE = "analysis_history.csv"

# Function to save analysis history to a CSV file
def save_analysis_history(history):
    """Save analysis history to a CSV file."""
    pd.concat(history).to_csv(HISTORY_FILE, index=False)

# Function to load analysis history from a CSV file
def load_analysis_history():
    """Load analysis history from a CSV file."""
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame()

# Function to perform login
def login():
    """Displays login form and validates user input."""
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

def fetch_data(current_cash, input_volume_24h):
    # Define API endpoints
    base_url = "https://prices.runescape.wiki/api/v1/osrs"
    latest_endpoint = f"{base_url}/latest"
    history_5m_endpoint = f"{base_url}/5m"
    history_1h_endpoint = f"{base_url}/1h"
    history_24h_endpoint = f"{base_url}/24h"
    mapping_endpoint = f"{base_url}/mapping"

    # Fetch data from endpoints
    latest_data = requests.get(latest_endpoint).json()
    history_5m_data = requests.get(history_5m_endpoint).json()
    history_1h_data = requests.get(history_1h_endpoint).json()
    history_24h_data = requests.get(history_24h_endpoint).json()
    item_mapping = requests.get(mapping_endpoint).json()

    # Parse item data and create a mapping of item IDs to their names and buy limits
    items = {str(item['id']): item['name'] for item in item_mapping}
    buy_limits = {str(item['id']): item.get('limit', float('inf')) for item in item_mapping}  # Ensure no limit means unlimited

    # Initialize a list to store items with their price information
    items_for_analysis = []

    # generate a unique session ID
    session_id = randint(1, 10000)

    # Analyze data
    for item_id, item_data in latest_data['data'].items():
        if (item_id in history_24h_data['data'] and 
            item_id in history_1h_data['data'] and 
            item_id in history_5m_data['data']):
            
            latest_low = item_data['low']
            latest_high = item_data['high']
            
            # avg_5m_low = history_5m_data['data'][item_id]['avgLowPrice']
            # avg_5m_high = history_5m_data['data'][item_id]['avgHighPrice']
            
            # avg_1h_low = history_1h_data['data'][item_id]['avgLowPrice']
            # avg_1h_high = history_1h_data['data'][item_id]['avgHighPrice']
            
            # avg_24h_low = history_24h_data['data'][item_id]['avgLowPrice']
            # avg_24h_high = history_24h_data['data'][item_id]['avgHighPrice']
            
            volume_24h = history_24h_data['data'][item_id]['lowPriceVolume']

            # Calculate the potential profit margin for quick flip
            if latest_low and latest_high and volume_24h:
                # filter on volume
                if volume_24h > input_volume_24h:

                    profit_margin = latest_high - latest_low - floor(latest_high * 0.01)

                    # Calculate maximum affordable quantity based on current cash and item buy limit
                    max_affordable_qty = min(current_cash // latest_low, buy_limits[item_id])

                    # calculate the potential profit
                    profit =  profit_margin * max_affordable_qty

                    # calculate the profit x volume for filtering purpose
                    profit_volume = profit * volume_24h

                    # filter on profit
                    if max_affordable_qty > 0:
                        # Store relevant information in the list
                        items_for_analysis.append({
                            'name': items.get(item_id, 'Unknown'),  # Ensure correct name matching
                            'Recommended Buy Price': latest_low,
                            'Recommended Sell Price': latest_high,
                            'Profit': profit,
                            'Max Qty Affordable': max_affordable_qty,
                            'Profit X Volume': profit_volume,
                            'Session ID': session_id,
                        })

    # Sort the list by volume (descending) first, then by highest profit margin (24h)
    items_for_analysis = sorted(
        items_for_analysis, 
        key=lambda x: (x['Profit X Volume']), 
        reverse=True
    )

    return items_for_analysis[:50]  # Return top 10 items for flipping

# Streamlit App
def main():
    # Initialize session state for login and history
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'analysis_history' not in st.session_state:
        # Load analysis history from file if available
        st.session_state.analysis_history = []
        loaded_history = load_analysis_history()
        if not loaded_history.empty:
            # Split loaded data into separate analyses
            unique_runs = loaded_history.groupby('Session ID').ngroup()
            for _, group in loaded_history.groupby(unique_runs):
                st.session_state.analysis_history.append(group)
    
    # Login section
    if not st.session_state.logged_in:
        login()
    else:
        st.title("OSRS Quick Flip Analyzer")
        
        # Input widgets with formatted input
        input_volume_24h = st.number_input("Enter the minimum 24h volume of the item to list:", min_value=1, value=90000, step=1)
        current_cash = st.number_input("Enter your available cash (in millions):", min_value=1.0, value=10.0, step=0.1, format="%.1f") * 1_000_000

        if st.button("Run Analysis"):
            with st.spinner("Fetching data and running analysis..."):
                try:
                    top_items = fetch_data(current_cash, input_volume_24h)
                    if top_items:
                        st.success("Analysis complete! Here are your top 10 items for quick flipping:")
                        
                        # Convert the results to a pandas DataFrame for better formatting
                        df = pd.DataFrame(top_items)
                        st.dataframe(df)  # Display the DataFrame in a nice, interactive table
                        
                        # Append current analysis to history
                        st.session_state.analysis_history.append(df)
                        
                        # Keep only the last 3 analyses
                        if len(st.session_state.analysis_history) > 3:
                            st.session_state.analysis_history.pop(0)
                        
                        # Save the updated history to a file
                        save_analysis_history(st.session_state.analysis_history)
                    else:
                        st.warning("No items found with the specified criteria.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")

        if st.session_state.analysis_history:
            # Display history
            st.write("### Previous Analyses:")
            for i, past_df in enumerate(reversed(st.session_state.analysis_history)):
                st.write(f"#### Analysis {i + 1}")
                st.dataframe(past_df)

if __name__ == "__main__":
    main()
