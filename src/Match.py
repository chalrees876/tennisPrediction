def handle_serve(pt1, pt2, set_score, game_score, point_score, server, returner, point_winner, serve, shot, error):
    serve_event_headers = ['serve_num',
                            'serve_direction',
                            'is_fault',
                            'miss_type',
                            'is_ace',
                            'snv',
                            'match_id',
                            'set_score'
                            'game_score',
                            'point_score',
                            'server',
                            'returner',
                            'point_winner']
    serve_num = 1
    serve_direction = None
    is_fault = False
    miss_type = None
    is_ace = False
    snv = False
    set_score = set_score
    game_score = game_score
    point_score = point_score
    server = server
    returner = returner
    point_winner = point_winner


    for s1, s2 in zip(pt1, pt2):
        if "c" in s1:
            s1 = s1.replace("c","") # removing lets
        if "c" in s2:
            s2 = s2.replace("c","")
        c1 = s1[:1] # first serve direction
        o1 = s1[1:2] # first serve outcome
        c2 = s2[:1] # second serve direction
        o2 = s2[1:2] # second serve outcome

        snv1 = False #serve and volley on first serve = false
        snv2 = False #serve and volley on second serve = false

        if o1 == "+":
            o1=s1[2:3]
            snv1 = True
        if o2 == "+":
            o2=s2[2:3]
            snv2 = True

        direction = serve[c1]  # set direction to first serve direction
        ace = False  # set ace to false
        miss = None
        serve_number = 1

        if o1 in error: # if first serve is missed, update miss to firstmiss
            miss = error[o1]
            server.update_serves(direction, miss, ace, snv1, serve_number)

            direction = serve[c2] # set direction to second serve direction
            serve_number = 2 # update serve number

            if o2 in shot: # if second serve made
                miss = None # set miss to none
                if o2 == "*":
                    ace = True
                    server.aces += 1
                server.update_serves(direction, miss, ace, snv2, serve_number)


            elif o2 in error: # if second serve is missed
                miss = error[o2]
                server.double_faults += 1
                server.update_serves(direction, miss, ace, snv2, serve_number)
            else:
                print("error, second serve not found: ", c2, "or", o2)

        elif o1 == "*":
            ace = True
            server.aces += 1
            server.update_serves(direction, miss, ace, snv1, serve_number)

        elif o1 in shot: # first serve made

        else:
            print("error, first serve not found in: ", o1, "or", c1, s1)

class Match:
    def __init__(self, match_id, player1, player2):
        self.match_id = match_id
        self.players = [player1, player2]
        self.serve_event_headers = ['serve_num',
                             'serve_direction',
                             'is_fault',
                             'miss_type',
                             'is_ace',
                             'snv',
                             'match_id',
                             'set_score'
                             'game_score',
                             'point_score',
                             'server',
                             'returner',
                             'point_winner']
        self.serve_events = []


    def add_serve_event(self, row):
        self.serve_events.append({"serve_num": })

    def get_match(self, match_id):
        return self.match_id