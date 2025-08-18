from asyncio import start_server


class Player:
    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name
        self.shots = []
        self.serves = []
        self.first_serve_percent = 0.0
        self.second_serve_percent = 0.0
        self.first_serve_win_percent = 0.0
        self.second_serve_win_percent = 0.0


    def handle_serve(self, pt1, pt2, serve, shot, error):
        for s1, s2 in zip(pt1, pt2):
            c1 = s1[:1] # first serve direction
            o1 = s1[1:2] # first serve outcome
            c2 = s2[:1] # second serve direction
            o2 = s2[1:2] # second serve outcome

            if o1 in error: # if first serve is missed, add missed serve to total serves
                self.serves.append({"direction": serve[c1],
                                    "miss": error[o1],
                                    "ace": False,
                                    "serve_number": 1})
                if o2 in error: # if second serve is missed, add missed serve to total serves
                    self.serves.append({"direction": serve[c2],
                                        "miss": error[o2],
                                        "ace": False,
                                        "serve_number": 2})
                elif o2 == "*":
                    self.serves.append({"direction": serve[c2],
                                        "miss": None,
                                        "ace": True,
                                        "serve_number": 2})
                elif o2 in shot: # if second serve is made in
                    self.serves.append({"direction": serve[c2],
                                        "miss": None,
                                        "ace": False,
                                        "serve_number": 2})
                else:
                    print("error, shot1 not found in : ", o1, "or", o2)

            elif o1 == "*":
                self.serves.append({"direction": serve[c1],
                                    "miss": None,
                                    "ace": True,
                                    "serve_number": 1})
            elif o1 in shot:
                self.serves.append({"direction": serve[c1],
                                    "miss": None,
                                    "ace": False,
                                    "serve_number": 1})

            else:
                print("error, shot2 not found in: ", o1, "or", o2)

