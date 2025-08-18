from asyncio import start_server


class Player:
    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name
        self.shots = []
        self.winners = 0
        self.unforced_errors = 0
        self.serves = []
        self.total_first_serves = 0
        self.made_first_serves = 0
        self.total_second_serves = 0
        self.made_second_serves = 0
        self.first_serve_percent = 0.0
        self.second_serve_percent = 0.0
        self.first_serve_win_percent = 0.0
        self.second_serve_win_percent = 0.0
        self.aces = 0
        self.double_faults = 0

    def update_serves(self, direction, miss, ace, snv, serve_number):
        if miss is None: # server did not miss
            if serve_number == 1:
                self.total_first_serves += 1
                self.made_first_serves += 1
            elif serve_number == 2:
                self.total_second_serves += 1
                self.made_second_serves += 1
        if miss is not None:
            if serve_number == 1:
                self.total_first_serves += 1
            elif serve_number == 2:
                self.total_second_serves += 1


        self.serves.append({"direction": direction,
                            "miss": miss,
                            "ace": ace,
                            "serve and volley": snv,
                            "serve number": serve_number})

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def add_shot(self, stroke, direction, depth, error, forced, winner):
        if error is not None and forced is False:
            self.unforced_errors += 1
        if winner is True:
            self.winners += 1
        self.shots.append(
            {"stroke": stroke,
             "direction": direction,
             "depth": depth,
             "error": error,
             "forced": forced,
             "winner": winner
             }
        )

