from src.gmail_api import GmailApi

g = GmailApi("./attachments", None)
g.get_all_labels()