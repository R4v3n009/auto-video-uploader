import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

class AccountManager:
    ACCOUNTS_FILE = 'accounts.json'
    TOKENS_DIR = 'tokens'
    CLIENT_SECRETS_FILE = "client_secret.json"
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

    def __init__(self):
        self.accounts = []
        os.makedirs(self.TOKENS_DIR, exist_ok=True)
        self.load_accounts()

    def load_accounts(self):
        if os.path.exists(self.ACCOUNTS_FILE):
            with open(self.ACCOUNTS_FILE, 'r') as f:
                self.accounts = json.load(f)
        else:
            self.accounts = []

    def save_accounts(self):
        with open(self.ACCOUNTS_FILE, 'w') as f:
            json.dump(self.accounts, f, indent=4)

    def get_accounts(self):
        return self.accounts

    def add_account(self) -> (bool, str):
        """
        Runs the full OAuth2 flow to add a new account.
        Returns (success, message_or_error)
        """
        try:
            if not os.path.exists(self.CLIENT_SECRETS_FILE):
                return False, f"'{self.CLIENT_SECRETS_FILE}' not found."

            flow = InstalledAppFlow.from_client_secrets_file(self.CLIENT_SECRETS_FILE, self.SCOPES)
            creds = flow.run_local_server(port=0)

            # Get channel info to use as a friendly name
            service = build('youtube', 'v3', credentials=creds)
            response = service.channels().list(part='snippet', mine=True).execute()
            
            if not response.get('items'):
                return False, "Could not retrieve channel information for this account."

            channel_info = response['items'][0]
            channel_id = channel_info['id']
            channel_title = channel_info['snippet']['title']
            account_name = f"{channel_title} ({channel_id})"

            # Check if account already exists
            if any(acc['id'] == channel_id for acc in self.accounts):
                return False, f"Account '{account_name}' is already linked."

            # Save the new token
            token_file_path = os.path.join(self.TOKENS_DIR, f'token_{channel_id}.pickle')
            with open(token_file_path, 'wb') as token:
                pickle.dump(creds, token)

            self.accounts.append({
                'id': channel_id,
                'name': account_name,
                'token_file': token_file_path
            })
            self.save_accounts()
            return True, f"Successfully added account: {account_name}"

        except Exception as e:
            return False, f"Failed to add account: {e}"

    def remove_account(self, account_id_to_remove: str):
        account_to_remove = next((acc for acc in self.accounts if acc['id'] == account_id_to_remove), None)
        if account_to_remove:
            # Remove token file
            if os.path.exists(account_to_remove['token_file']):
                os.remove(account_to_remove['token_file'])
            
            # Remove from list and save
            self.accounts = [acc for acc in self.accounts if acc['id'] != account_id_to_remove]
            self.save_accounts()