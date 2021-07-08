import gspread


class GoogleSheet:
    _service = None

    @staticmethod
    def get_service():
        if GoogleSheet._service is None:
            GoogleSheet._service = gspread.service_account(filename="client_secret.json")

        return GoogleSheet._service
