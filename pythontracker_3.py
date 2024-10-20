import pandas as pd
import plotly.express as px
import os
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# Path to the directory where CSV files are stored
CSV_DIRECTORY = "/root/quiltracker"

# Disable caching for browser
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Function to get the latest price of Wrapped Quil (wQUIL) from CoinGecko
def get_wquil_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': 'wrapped-quil',
        'vs_currencies': 'usd'
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data['wrapped-quil']['usd']
    except Exception as e:
        print(f"Error fetching wQUIL price: {e}")
        return 0

# Compute Quil earned per minute, per hour, and earnings
def compute_metrics(df, wquil_price):
    df['Date'] = pd.to_datetime(df['Date'])
    df['Balance'] = df['Balance'].astype(float)

    # Calculate Quil earned per minute
    df['Time_Diff_Minutes'] = df.groupby('Peer ID')['Date'].diff().dt.total_seconds() / 60
    df['Quil_Per_Minute'] = df.groupby('Peer ID')['Balance'].diff() / df['Time_Diff_Minutes']
    df['Quil_Per_Minute'] = df['Quil_Per_Minute'].fillna(0)

    # Filter out large time gaps to avoid incorrect calculations
    df = df.loc[df['Time_Diff_Minutes'] < 120]

    # Calculate Quil per hour
    df['Quil_Per_Hour'] = df['Quil_Per_Minute'] * 60

    # Calculate earnings per hour in USD
    df['Earnings_Per_Hour'] = df['Quil_Per_Hour'] * wquil_price

    # Add metrics to the original DataFrame
    df['Quil Per Day'] = df['Balance']  # Adjust this as per your logic
    df['Earnings_Per_Day'] = df['Earnings_Per_Hour'] * 24

    return df  # Return the modified DataFrame with all metrics

# Function to calculate Quil earned in the last 1,440 minutes (24 hours)
def calculate_last_1440_minutes(df):
    # Sort by date
    df = df.sort_values('Date')

    # Calculate the growth (quil earned) for the last 1,440 records for each peer
    last_1440_values = df.groupby('Peer ID').tail(1440)

    # Calculate Quil per day by comparing the first and last values of these 1,440 records
    last_1440_quil_per_day = last_1440_values.groupby('Peer ID')['Balance'].last() - last_1440_values.groupby('Peer ID')['Balance'].first()

    return last_1440_quil_per_day

# Calculate 24-hour Quil Per Hour based on the last 1,440 minutes
def calculate_last_1440_minutes_quil_per_hour(df):
    # Sort by date
    df = df.sort_values('Date')

    # Calculate the growth (quil earned) for the last 1,440 records for each peer
    last_1440_values = df.groupby('Peer ID').tail(1440)

    # Calculate Quil per hour
    last_1440_quil_per_hour = (last_1440_values.groupby('Peer ID')['Balance'].last() - 
                               last_1440_values.groupby('Peer ID')['Balance'].first()) / 24

    return last_1440_quil_per_hour

# Route to update balance data
@app.route('/update_balance', methods=['POST'])
def update_balance():
    try:
        data = request.get_json()
        print(f"Received data: {data}")

        if not data or 'peer_id' not in data or 'balance' not in data or 'timestamp' not in data or 'hostname' not in data:
            return 'Invalid data', 400

        peer_id = data['peer_id']
        balance = data['balance']
        timestamp = data['timestamp']
        hostname = data['hostname']

        log_file = os.path.join(CSV_DIRECTORY, f'node_balance_{peer_id}.csv')

        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                f.write('Date,Peer ID,Hostname,Balance\n')

        with open(log_file, 'a') as f:
            f.write(f'{timestamp},{peer_id},{hostname},{balance}\n')

        print(f"Logged balance for {peer_id} ({hostname}): {balance} at {timestamp}")
        return 'Balance updated', 200
    except Exception as e:
        print(f"Error updating balance: {e}")
        return 'Internal Server Error', 500

# Main dashboard route
@app.route('/')
def index():
    wquil_price = get_wquil_price()
    data_frames = []
    night_mode = request.args.get('night_mode', 'off')

    # Read and combine all CSV files
    for file_name in os.listdir(CSV_DIRECTORY):
        if file_name.endswith('.csv'):
            file_path = os.path.join(CSV_DIRECTORY, file_name)
            print(f"Reading CSV file: {file_path}")
            df = pd.read_csv(file_path)

            # Ensure 'Balance' is numeric
            if df['Balance'].dtype == 'object':
                df['Balance'] = df['Balance'].str.extract(r'([\d\.]+)').astype(float)

            # Print columns to debug
            print(f"Columns in {file_name}: {df.columns.tolist()}")

            data_frames.append(df)

    # Combine data into a single DataFrame
    if data_frames:
        combined_df = pd.concat(data_frames)
        combined_df['Date'] = pd.to_datetime(combined_df['Date'])
        combined_df.sort_values('Date', inplace=True)
        combined_df.columns = combined_df.columns.str.strip()

        # Print columns to debug
        print("Columns in combined DataFrame:", combined_df.columns.tolist())

        # Compute metrics
        combined_df = compute_metrics(combined_df, wquil_price)

        # Remove duplicates and keep the most recent balance for each Peer ID
        latest_balances = combined_df.groupby('Peer ID').last().reset_index()
        latest_balances['Hostname'] = combined_df.groupby('Peer ID')['Hostname'].last()

        # Print available columns
        print("Columns in latest_balances:", latest_balances.columns.tolist())

        # Prepare table data for rendering
        table_data = latest_balances[['Hostname', 'Balance', 'Quil Per Day', 'Earnings_Per_Day', 
                                       'Quil_Per_Minute', 'Quil_Per_Hour', 'Earnings_Per_Hour']].reset_index()
    else:
        table_data = []

    return render_template('index.html', table_data=table_data)

if __name__ == '__main__':
    app.run(host='192.168.20.210', port=5000, debug=True)