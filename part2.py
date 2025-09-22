from dotenv import load_dotenv
import streamlit as st
import json
import os
import csv
import time
from datetime import datetime
import requests
import pandas as pd  # For CSV handling

load_dotenv()

# Files
NUMBERS_CSV = "numbers.csv"
DEALS_FILE = "deals.json"
ASSISTANTS_FILE = "assistants.json"

# Load numbers from CSV
def load_numbers():
    if not os.path.exists(NUMBERS_CSV):
        st.warning("numbers.csv not found. Create it with columns: Phone Number, Country, Type, Raw Number")
        return pd.DataFrame(columns=['phone', 'name', 'status', 'country', 'type', 'raw_number'])

    try:
        df = pd.read_csv(NUMBERS_CSV)
        print(f"DEBUG: Loaded CSV with columns: {list(df.columns)}")
        print(f"DEBUG: CSV shape: {df.shape}")

        # Map the CSV columns to our expected format
        if 'Phone Number' in df.columns:
            df['phone'] = df['Phone Number']
            df['name'] = df.get('Country', 'Unknown')
            df['country'] = df.get('Country', 'Unknown')
            df['type'] = df.get('Type', 'Unknown')
            df['raw_number'] = df.get('Raw Number', df['Phone Number'])
            print("DEBUG: Successfully mapped CSV columns")
        else:
            print("DEBUG: 'Phone Number' column not found in CSV")
            # If no Phone Number column, try to use first column as phone
            if len(df.columns) > 0:
                df['phone'] = df.iloc[:, 0]
                df['name'] = 'Unknown'
                df['country'] = 'Unknown'
                df['type'] = 'Unknown'
                df['raw_number'] = df.iloc[:, 0]

        # Add status column if it doesn't exist
        if 'status' not in df.columns:
            df['status'] = 'pending'
            print("DEBUG: Added status column")

        # Add last_called column if it doesn't exist
        if 'last_called' not in df.columns:
            df['last_called'] = None
            print("DEBUG: Added last_called column")

        result_df = df[['phone', 'name', 'status', 'country', 'type', 'raw_number', 'last_called']]
        print(f"DEBUG: Final DataFrame columns: {list(result_df.columns)}")
        print(f"DEBUG: Final DataFrame shape: {result_df.shape}")

        return result_df

    except Exception as e:
        st.error(f"Error loading CSV: {str(e)}")
        print(f"DEBUG: Error loading CSV: {str(e)}")
        return pd.DataFrame(columns=['phone', 'name', 'status', 'country', 'type', 'raw_number'])

# Save numbers to CSV
def save_numbers(df):
    # Prepare the dataframe for CSV export
    export_df = df.copy()

    # Map back to CSV format if needed
    if 'phone' in export_df.columns:
        export_df['Phone Number'] = export_df['phone']
        export_df['Country'] = export_df.get('name', 'Unknown')
        export_df['Type'] = export_df.get('type', 'Mobile')
        export_df['Raw Number'] = export_df.get('raw_number', export_df['phone'])

    # Keep only the original CSV columns for export
    csv_columns = ['Phone Number', 'Country', 'Type', 'Raw Number']
    export_columns = [col for col in csv_columns if col in export_df.columns]

    export_df[csv_columns].to_csv(NUMBERS_CSV, index=False)

# Load deals
def load_deals():
    if not os.path.exists(DEALS_FILE):
        return []
    with open(DEALS_FILE, 'r') as f:
        return json.load(f)

# Get pending numbers
def get_pending_numbers():
    df = load_numbers()
    if 'status' in df.columns:
        return df[df['status'] == 'pending']
    else:
        return pd.DataFrame(columns=df.columns)

# Get done numbers
def get_done_numbers():
    df = load_numbers()
    if 'status' in df.columns:
        return df[df['status'] == 'done']
    else:
        return pd.DataFrame(columns=df.columns)

# Assistant management functions
def save_assistant(assistant_data):
    """Save assistant data to JSON file"""
    try:
        assistants = load_assistants()
        # Check if assistant already exists
        existing_index = None
        for i, assistant in enumerate(assistants):
            if assistant.get('id') == assistant_data.get('id'):
                existing_index = i
                break

        if existing_index is not None:
            assistants[existing_index] = assistant_data
        else:
            assistants.append(assistant_data)

        with open(ASSISTANTS_FILE, 'w') as f:
            json.dump(assistants, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error saving assistant: {str(e)}")
        return False

def load_assistants():
    """Load assistants from JSON file"""
    if not os.path.exists(ASSISTANTS_FILE):
        return []
    try:
        with open(ASSISTANTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def delete_assistant(assistant_id):
    """Delete an assistant from local storage"""
    try:
        assistants = load_assistants()
        assistants = [a for a in assistants if a.get('id') != assistant_id]
        with open(ASSISTANTS_FILE, 'w') as f:
            json.dump(assistants, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error deleting assistant: {str(e)}")
        return False

# Lead and deal management functions
def update_lead_status_after_call(phone, new_status):
    """Update lead status after a call is completed"""
    try:
        df = load_numbers()

        # Find the lead by phone number
        mask = df['phone'] == phone
        if not df[mask].empty:
            # Update the status
            df.loc[mask, 'status'] = new_status
            df.loc[mask, 'last_called'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Save the updated dataframe
            save_numbers(df)
            return True, f"Lead {phone} status updated to {new_status}"
        else:
            return False, f"Lead with phone {phone} not found"

    except Exception as e:
        return False, f"Error updating lead status: {str(e)}"

def save_closed_deal(deal_data):
    """Save a closed deal to deals.json"""
    try:
        # Load existing deals
        deals = load_deals()

        # Add timestamp if not provided
        if 'timestamp' not in deal_data:
            deal_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add unique ID if not provided
        if 'id' not in deal_data:
            deal_data['id'] = f"deal_{len(deals) + 1}_{int(time.time())}"

        # Append the new deal
        deals.append(deal_data)

        # Save to file
        with open(DEALS_FILE, 'w') as f:
            json.dump(deals, f, indent=4)

        return True, f"Deal saved successfully: {deal_data.get('id', 'Unknown')}"

    except Exception as e:
        return False, f"Error saving deal: {str(e)}"

def handle_call_completion_events(call_id, phone, outcome, call_summary=None):
    """
    Handle call completion events and update records

    Args:
        call_id: The Vapi call ID
        phone: The phone number that was called
        outcome: The outcome of the call ('completed', 'no_answer', 'busy', 'failed', 'deal_closed')
        call_summary: Optional summary of the call
    """
    try:
        results = []

        # Update lead status based on outcome
        if outcome == 'deal_closed':
            status = 'done'  # Mark as done for closed deals
        elif outcome in ['no_answer', 'busy']:
            status = 'pending'  # Keep as pending for retry
        elif outcome == 'completed':
            status = 'done'  # Mark as done for completed calls
        else:
            status = 'failed'  # Mark as failed for other outcomes

        success, message = update_lead_status_after_call(phone, status)
        results.append(f"Status update: {message}")

        # If deal was closed, save the deal
        if outcome == 'deal_closed':
            deal_data = {
                'call_id': call_id,
                'phone': phone,
                'outcome': outcome,
                'summary': call_summary or 'Deal closed successfully',
                'status': 'closed'
            }

            success, message = save_closed_deal(deal_data)
            results.append(f"Deal save: {message}")

        # Log the call completion
        log_call_completion(call_id, phone, outcome, call_summary)

        return True, "Call completion handled successfully", results

    except Exception as e:
        error_msg = f"Error handling call completion: {str(e)}"
        return False, error_msg, []

def log_call_completion(call_id, phone, outcome, summary=None):
    """Log call completion to call history"""
    try:
        # Load existing call history
        if os.path.exists('call_history.json'):
            with open('call_history.json', 'r') as f:
                call_history = json.load(f)
        else:
            call_history = []

        # Add new call record
        call_record = {
            'call_id': call_id,
            'phone': phone,
            'outcome': outcome,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': summary
        }

        call_history.append(call_record)

        # Save to file
        with open('call_history.json', 'w') as f:
            json.dump(call_history, f, indent=4)

    except Exception as e:
        print(f"Error logging call completion: {str(e)}")

# Vapi API integration
class VapiAI:
    def __init__(self):
        self.api_key = None
        
    def setup_api_key(self, api_key=None):
        """Setup Vapi API key"""
        if api_key:
            self.api_key = api_key
            return True
        
        # Try to get from environment variables
        env_api_key = os.getenv("VAPI_API_KEY")
        if env_api_key:
            self.api_key = env_api_key
            return True
            
        # Try to get from session state
        if 'vapi_api_key' in st.session_state and st.session_state.vapi_api_key:
            self.api_key = st.session_state.vapi_api_key
            return True
            
        # Try to get from secrets
        try:
            if hasattr(st, 'secrets') and 'VAPI_API_KEY' in st.secrets:
                self.api_key = st.secrets['VAPI_API_KEY']
                return True
        except:
            pass
            
        return False
    
    def create_assistant(self, name, voice_id, first_message, model, instructions):
        """Create a Vapi assistant"""
        if not self.api_key:
            return None, "API key not configured"

        try:
            url = "https://api.vapi.ai/assistant"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "name": name,
                "firstMessage": first_message,
                "model": {
                    "provider": "openai",
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": instructions
                        }
                    ]
                },
                "voice": {
                    "provider": "11labs",
                    "voiceId": voice_id
                },
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-2",
                    "language": "en-US"
                },
                "maxDurationSeconds": 600,
                "interruptionsEnabled": True
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 201:
                assistant_data = response.json()
                # Save to local storage
                save_assistant(assistant_data)
                return assistant_data, None
            else:
                return None, f"API error: {response.status_code} - {response.text}"
        except Exception as e:
            return None, f"Error creating assistant: {str(e)}"

    def fetch_assistants(self):
        """Fetch all assistants from VAPI"""
        if not self.api_key:
            return []

        try:
            url = "https://api.vapi.ai/assistant"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                assistants_data = response.json()
                print(f"DEBUG: API Response type: {type(assistants_data)}")
                print(f"DEBUG: API Response content: {assistants_data}")

                # Handle different response structures
                if isinstance(assistants_data, list):
                    # If response is directly a list of assistants
                    assistants = assistants_data
                    print(f"DEBUG: Response is a list with {len(assistants)} items")
                elif isinstance(assistants_data, dict):
                    # If response is a dict with 'assistants' key
                    assistants = assistants_data.get('assistants', [])
                    print(f"DEBUG: Response is a dict, extracted {len(assistants)} assistants")
                else:
                    # Fallback
                    assistants = []
                    print("DEBUG: Response is neither list nor dict, using empty list")

                # Save all assistants to local storage
                for assistant in assistants:
                    save_assistant(assistant)

                return assistants
            else:
                st.error(f"API Error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            st.error(f"Error fetching assistants: {str(e)}")
            print(f"DEBUG: Exception details: {type(e).__name__}: {e}")
            return []

    def make_call(self, assistant_id, phone_number):
        """Make a call using Vapi"""
        if not self.api_key:
            return None, "API key not configured"

        try:
            url = "https://api.vapi.ai/call/phone"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Format phone number to E.164 if not already formatted
            if not phone_number.startswith('+'):
                phone_number = '+' + phone_number

            data = {
                "assistantId": assistant_id,
                "phoneNumber": {
                    "twilioPhoneNumber": phone_number,
                    "twilioAccountSid": os.getenv("TWILIO_ACCOUNT_SID")
                }
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 201:
                call_data = response.json()
                call_id = call_data.get("id")

                # Listen for interruptions and handle real-time transcription
                self.handle_real_time_interaction(call_id)

                # Wait for call completion and handle events
                self.wait_for_call_completion(call_id, phone_number)

                return call_data, None
            else:
                return None, f"API error: {response.status_code} - {response.text}"
        except Exception as e:
            return None, f"Error making call: {str(e)}"
    
    def handle_real_time_interaction(self, call_id):
        """Handle real-time interaction during a call"""
        try:
            url = f"https://api.vapi.ai/call/{call_id}/events"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            while True:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    events = response.json()

                    for event in events:
                        event_type = event.get("type")
                        print(f"Received event: {event_type}")  # Log event type

                        if event_type == "caller_speaking":
                            print("Caller is speaking. Pausing assistant...")
                            self.pause_assistant(call_id)

                        elif event_type == "caller_finished":
                            print("Caller finished speaking. Resuming assistant...")
                            self.resume_assistant(call_id)

                        elif event_type == "call_disconnected":
                            print("Caller disconnected abruptly. Logging the event...")
                            self.log_disconnection(call_id)
                            return
                else:
                    print(f"Error fetching events: {response.status_code} - {response.text}")
                    break
        except Exception as e:
            print(f"Error handling real-time interaction: {str(e)}")

    def pause_assistant(self, call_id):
        """Pause the assistant during a call"""
        try:
            url = f"https://api.vapi.ai/call/{call_id}/pause"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            requests.post(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"Error pausing assistant: {str(e)}")

    def resume_assistant(self, call_id):
        """Resume the assistant during a call"""
        try:
            url = f"https://api.vapi.ai/call/{call_id}/resume"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            requests.post(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"Error resuming assistant: {str(e)}")

    def wait_for_call_completion(self, call_id, phone_number):
        """Wait for call completion and handle events"""
        try:
            max_wait_time = 600  # Maximum 10 minutes wait
            check_interval = 10  # Check every 10 seconds
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                # Check call status
                call_status = self.get_call_status(call_id)

                if call_status:
                    status = call_status.get('status')

                    if status == 'ended':
                        # Call has ended, determine outcome
                        outcome = self.determine_call_outcome(call_status)
                        summary = call_status.get('summary', 'Call completed')

                        # Handle call completion events
                        success, message, results = handle_call_completion_events(
                            call_id, phone_number, outcome, summary
                        )

                        if success:
                            print(f"Call completion handled: {results}")
                        else:
                            print(f"Error handling call completion: {message}")

                        return True

                # Wait before next check
                time.sleep(check_interval)
                elapsed_time += check_interval

            # If we reach here, call is still ongoing after max wait time
            print(f"Call {call_id} still ongoing after {max_wait_time} seconds")
            return False

        except Exception as e:
            print(f"Error waiting for call completion: {str(e)}")
            return False

    def get_call_status(self, call_id):
        """Get the current status of a call"""
        if not self.api_key:
            return None

        try:
            url = f"https://api.vapi.ai/call/{call_id}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting call status: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error fetching call status: {str(e)}")
            return None

    def determine_call_outcome(self, call_status):
        """Determine the outcome of a call based on its status"""
        try:
            # Check if call was successful
            duration = call_status.get('duration', 0)
            status = call_status.get('status', 'unknown')

            if status == 'ended':
                # If call lasted more than 30 seconds, consider it completed
                if duration > 30:
                    return 'completed'
                else:
                    return 'no_answer'
            elif status == 'failed':
                return 'failed'
            else:
                return 'unknown'

        except Exception as e:
            print(f"Error determining call outcome: {str(e)}")
            return 'unknown'

    def get_assistants(self):
        """Get all assistants"""
        if not self.api_key:
            return []

        try:
            url = "https://api.vapi.ai/assistant"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                # Handle different response structures
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('assistants', [])
                else:
                    return []
            else:
                st.error(f"API Error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            st.error(f"Error fetching assistants: {str(e)}")
            return []

    def get_voices(self):
        """Fetch available voices from Vapi"""
        if not self.api_key:
            return []

        try:
            url = "https://api.vapi.ai/voices"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                # Handle different response structures
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('voices', [])
                else:
                    return []
            else:
                st.error(f"API Error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            st.error(f"Error fetching voices: {str(e)}")
            return []

    def start_whatsapp_conversation(self, assistant_id, whatsapp_number):
        """Start a WhatsApp conversation using Vapi"""
        if not self.api_key:
            return None, "API key not configured"

        try:
            # Try VAPI's messaging endpoint for WhatsApp
            url = "https://api.vapi.ai/message"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "assistantId": assistant_id,
                "channel": {
                    "type": "whatsapp",
                    "number": whatsapp_number
                },
                "message": {
                    "type": "text",
                    "text": "Hello! I'm starting our conversation. How can I help you today?"
                }
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 201:
                conversation_data = response.json()
                conversation_id = conversation_data.get("id")
                return conversation_data, None
            elif response.status_code == 404:
                # VAPI might not support WhatsApp directly, provide alternative
                return None, "WhatsApp not supported by VAPI. Consider using Twilio WhatsApp API or VAPI voice calls instead."
            else:
                return None, f"API error: {response.status_code} - {response.text}"
        except Exception as e:
            return None, f"Error starting WhatsApp conversation: {str(e)}"

    def send_whatsapp_message(self, conversation_id, message):
        """Send a message in WhatsApp conversation"""
        if not self.api_key:
            return None, "API key not configured"

        try:
            url = "https://api.vapi.ai/message"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "conversationId": conversation_id,
                "type": "whatsapp",
                "message": {
                    "type": "text",
                    "text": message
                }
            }
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"API error: {response.status_code} - {response.text}"
        except Exception as e:
            return None, f"Error sending WhatsApp message: {str(e)}"

    def get_conversation_history(self, conversation_id):
        """Get conversation history"""
        if not self.api_key:
            return []

        try:
            url = f"https://api.vapi.ai/message?conversationId={conversation_id}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"DEBUG: Conversation history response type: {type(data)}")
                if isinstance(data, dict):
                    return data.get('messages', [])
                elif isinstance(data, list):
                    return data
                else:
                    return []
            else:
                return []
        except Exception as e:
            return []

    def end_whatsapp_conversation(self, conversation_id):
        """End a WhatsApp conversation"""
        if not self.api_key:
            return False, "API key not configured"

        try:
            url = f"https://api.vapi.ai/message/{conversation_id}/end"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code == 200, None
        except Exception as e:
            return False, f"Error ending conversation: {str(e)}"

# Initialize APIs
vapi_ai = VapiAI()
vapi_ai.setup_api_key()  # Load API key from environment

# Main application for outbound calling
def main():
    st.set_page_config(
        page_title="Outbound Calling App",
        page_icon="📞",
        layout="wide"
    )
    
    st.title("📞 Outbound Sales Calling App")
    st.markdown("### AI-powered outbound calls to close deals from CSV leads")
    
    # Check Vapi API
    if not vapi_ai.api_key:
        st.error("VAPI_API_KEY not set in .env. Please configure it.")
        st.stop()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Leads", "🤖 Assistants", "🚀 Start Calls", "📊 Deals", "📞 Call History"])
    
    with tab1:
        st.subheader("📋 Load and Manage Leads")
        df = load_numbers()

        # Lead statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_leads = len(df)
            st.metric("Total Leads", total_leads)

        with col2:
            pending_leads = len(df[df['status'] == 'pending']) if 'status' in df.columns else 0
            st.metric("Pending", pending_leads)

        with col3:
            done_leads = len(df[df['status'] == 'done']) if 'status' in df.columns else 0
            st.metric("Done", done_leads)

        with col4:
            failed_leads = len(df[df['status'] == 'failed']) if 'status' in df.columns else 0
            st.metric("Failed", failed_leads)

        # Display leads with enhanced information
        if not df.empty:
            # Add some formatting to the dataframe
            display_df = df.copy()
            display_df['status'] = display_df['status'].map({
                'pending': '⏳ Pending',
                'done': '✅ Done',
                'failed': '❌ Failed'
            }).fillna(display_df['status'])

            # Show relevant columns
            display_columns = ['phone', 'name', 'status', 'type', 'last_called']
            available_columns = [col for col in display_columns if col in display_df.columns]
            st.dataframe(display_df[available_columns], width='stretch')

            # Manual status update
            st.subheader("🔄 Update Lead Status")
            col1, col2, col3 = st.columns(3)

            with col1:
                update_phone = st.text_input("Phone Number", placeholder="Enter phone number")

            with col2:
                new_status = st.selectbox("New Status", ["pending", "done", "failed"])

            with col3:
                if st.button("Update Status", type="primary"):
                    if update_phone:
                        success, message = update_lead_status_after_call(update_phone, new_status)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("Please enter a phone number.")

        # Upload new CSV
        st.subheader("📁 Upload New Leads")
        uploaded_file = st.file_uploader("Upload numbers.csv", type="csv")
        if uploaded_file:
            df = pd.read_csv(uploaded_file)

            # Map CSV columns to our format
            if 'Phone Number' in df.columns:
                df['phone'] = df['Phone Number']
                df['name'] = df.get('Country', 'Unknown')
                df['country'] = df.get('Country', 'Unknown')
                df['type'] = df.get('Type', 'Mobile')
                df['raw_number'] = df.get('Raw Number', df['Phone Number'])

            # Add status and last_called columns if they don't exist
            if 'status' not in df.columns:
                df['status'] = 'pending'
            if 'last_called' not in df.columns:
                df['last_called'] = None

            # Keep only our working columns
            df = df[['phone', 'name', 'status', 'country', 'type', 'raw_number', 'last_called']]

            save_numbers(df)
            st.success("✅ CSV updated successfully!")
            st.rerun()

    with tab2:
        st.subheader("🤖 AI Assistants Management")

        # Fetch existing assistants from VAPI
        if st.button("🔄 Fetch Assistants from VAPI", type="primary"):
            with st.spinner("Fetching assistants from VAPI..."):
                assistants = vapi_ai.fetch_assistants()
                if assistants:
                    st.success(f"Found {len(assistants)} assistants")
                    st.session_state.assistants_list = assistants
                else:
                    st.warning("No assistants found on VAPI")

        # Load local assistants
        local_assistants = load_assistants()

        if local_assistants:
            st.subheader("📋 Your Assistants")

            for i, assistant in enumerate(local_assistants):
                # Safety check for assistant data
                if not isinstance(assistant, dict):
                    st.error(f"Invalid assistant data at index {i}")
                    continue

                assistant_name = assistant.get('name', 'Unnamed Assistant')
                assistant_id = assistant.get('id', 'No ID')

                with st.expander(f"🤖 {assistant_name} - {assistant_id[:8]}..."):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        model_info = assistant.get('model', {})
                        if isinstance(model_info, dict):
                            model_name = model_info.get('model', 'Unknown')
                        else:
                            model_name = str(model_info) if model_info else 'Unknown'
                        st.write(f"**Model**: {model_name}")
                        st.write(f"**Created**: {assistant.get('createdAt', 'Unknown')}")
                        st.write(f"**Status**: {'✅ Active' if assistant.get('id') else '❌ Inactive'}")

                    with col2:
                        if st.button(f"Select", key=f"select_{i}"):
                            st.session_state.sales_assistant_id = assistant.get('id')
                            st.success(f"Selected: {assistant_name}")
                            st.rerun()

                        if st.button(f"Delete", key=f"delete_{i}"):
                            if delete_assistant(assistant.get('id')):
                                st.success(f"Deleted: {assistant_name}")
                                st.rerun()

        # Create new assistant
        st.subheader("➕ Create New Assistant")

        with st.form("create_assistant_form"):
            assistant_name = st.text_input("Assistant Name", value="Sales Assistant")
            voice_id = st.text_input("Voice ID", value="21m00Tcm4TlvDq8ikWAM")
            first_message = st.text_input("First Message", value="Hello! Thank you for calling. May I know your name, please?")
            model = st.selectbox("AI Model", ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"], index=0)
            instructions = st.text_area("Instructions",
                value="You are a professional sales assistant. Be friendly, helpful, and focus on understanding customer needs and closing deals.",
                height=100)

            if st.form_submit_button("Create Assistant", type="primary"):
                with st.spinner("Creating assistant..."):
                    assistant_data, error = vapi_ai.create_assistant(
                        assistant_name, voice_id, first_message, model, instructions
                    )

                    if assistant_data:
                        # Safety check for assistant data
                        if isinstance(assistant_data, dict):
                            assistant_name = assistant_data.get('name', 'Unknown Assistant')
                            assistant_id = assistant_data.get('id', 'No ID')
                            st.success(f"✅ Assistant created: {assistant_name}")
                            st.session_state.sales_assistant_id = assistant_id
                        else:
                            st.success("✅ Assistant created successfully!")
                            st.session_state.sales_assistant_id = str(assistant_data)
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to create assistant: {error}")

    with tab3:
        st.subheader("Outbound Calling")
        
        pending_df = get_pending_numbers()
        if pending_df.empty:
            st.warning("No pending numbers. Add leads in the Leads tab.")
            st.stop()
        
        st.dataframe(pending_df, width='stretch')
        
        assistant_id = st.session_state.get('sales_assistant_id')
        if not assistant_id:
            st.warning("Please select or create an assistant in the Assistants tab first.")
            st.stop()

        st.info(f"📞 Using Assistant: {assistant_id}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Start Batch Calls", type="primary"):
                st.session_state.calling_batch = True
                st.rerun()

        if st.session_state.get('calling_batch', False):
                st.info("🚀 Starting batch calls...")

                progress_bar = st.progress(0)
                status_text = st.empty()

                total_calls = len(pending_df)
                completed_calls = 0

                for index, row in pending_df.iterrows():
                    phone = row['phone']
                    name = row.get('name', 'Unknown Contact')

                    # Update progress
                    progress = completed_calls / total_calls
                    progress_bar.progress(progress)
                    status_text.text(f"📞 Calling {name} ({phone})... ({completed_calls + 1}/{total_calls})")

                    # Make the call
                    success, msg = vapi_ai.make_call(assistant_id, phone)

                    if success:
                        st.success(f"✅ Call to {phone} initiated and completed")
                        completed_calls += 1
                    else:
                        st.error(f"❌ Failed to call {phone}: {msg}")
                        completed_calls += 1

                    # Small delay between calls to prevent overwhelming the system
                    time.sleep(5)

                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()

                st.session_state.calling_batch = False
                st.success(f"🎉 Batch calls completed! Processed {completed_calls} calls.")
                st.rerun()

    with tab4:
        st.subheader("📊 Closed Deals")

        # Manual deal entry
        st.subheader("➕ Add Manual Deal")
        with st.form("manual_deal_form"):
            col1, col2 = st.columns(2)

            with col1:
                manual_phone = st.text_input("Phone Number", placeholder="+1234567890")
                deal_amount = st.number_input("Deal Amount ($)", min_value=0.0, step=100.0)

            with col2:
                deal_summary = st.text_area("Deal Summary", height=100, placeholder="Describe the closed deal...")
                deal_status = st.selectbox("Status", ["closed", "pending", "lost"])

            if st.form_submit_button("💾 Save Deal", type="primary"):
                if manual_phone and deal_summary:
                    deal_data = {
                        'phone': manual_phone,
                        'amount': deal_amount,
                        'summary': deal_summary,
                        'status': deal_status,
                        'source': 'manual_entry'
                    }

                    success, message = save_closed_deal(deal_data)
                    if success:
                        st.success("✅ Deal saved successfully!")

                        # Update lead status to 'done' if deal is closed
                        if deal_status == 'closed':
                            update_lead_status_after_call(manual_phone, 'done')

                        st.rerun()
                    else:
                        st.error(f"❌ Error saving deal: {message}")
                else:
                    st.warning("Please provide phone number and deal summary.")

        # Display existing deals
        st.subheader("📋 All Deals")
        deals = load_deals()
        if deals:
            deals_df = pd.DataFrame(deals)
            st.dataframe(deals_df, width='stretch')

            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                total_deals = len(deals)
                st.metric("Total Deals", total_deals)

            with col2:
                closed_deals = len([d for d in deals if d.get('status') == 'closed'])
                st.metric("Closed Deals", closed_deals)

            with col3:
                total_amount = sum([d.get('amount', 0) for d in deals if d.get('status') == 'closed'])
                st.metric("Total Value", f"${total_amount:,.2f}")
        else:
            st.info("📈 No deals recorded yet. Start making calls or add deals manually!")

    with tab5:
        st.subheader("📞 Call History & Analytics")

        # Load call history
        if os.path.exists('call_history.json'):
            with open('call_history.json', 'r') as f:
                call_history = json.load(f)
        else:
            call_history = []

        if call_history:
            # Convert to DataFrame for better display
            history_df = pd.DataFrame(call_history)

            # Call outcome statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_calls = len(history_df)
                st.metric("Total Calls", total_calls)

            with col2:
                completed_calls = len(history_df[history_df['outcome'] == 'completed'])
                st.metric("Completed", completed_calls)

            with col3:
                closed_deals = len(history_df[history_df['outcome'] == 'deal_closed'])
                st.metric("Deals Closed", closed_deals)

            with col4:
                success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
                st.metric("Success Rate", f"{success_rate:.1f}%")

            # Display call history
            st.subheader("📋 Recent Calls")
            display_history = history_df.copy()
            display_history['outcome'] = display_history['outcome'].map({
                'completed': '✅ Completed',
                'deal_closed': '💰 Deal Closed',
                'no_answer': '📞 No Answer',
                'busy': '📵 Busy',
                'failed': '❌ Failed',
                'unknown': '❓ Unknown'
            }).fillna(display_history['outcome'])

            # Sort by timestamp (newest first)
            display_history = display_history.sort_values('timestamp', ascending=False)
            st.dataframe(display_history, width='stretch')

            # Clear call history option
            if st.button("🗑️ Clear Call History", type="secondary"):
                if st.checkbox("Are you sure? This cannot be undone."):
                    os.remove('call_history.json')
                    st.success("Call history cleared!")
                    st.rerun()
        else:
            st.info("📊 No call history yet. Start making calls to see analytics here!")

        # Quick stats from leads
        st.subheader("🎯 Lead Status Summary")
        df = load_numbers()
        if not df.empty:
            status_counts = df['status'].value_counts()
            col1, col2, col3 = st.columns(3)

            with col1:
                pending = status_counts.get('pending', 0)
                st.metric("Pending Leads", pending)

            with col2:
                done = status_counts.get('done', 0)
                st.metric("Completed Leads", done)

            with col3:
                failed = status_counts.get('failed', 0)
                st.metric("Failed Leads", failed)

if __name__ == "__main__":
    main()