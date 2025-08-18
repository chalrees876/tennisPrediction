import src.codes as codes


def handle_serve(pt1, pt2, serve, shot, error, server):
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
            server.update_serves(direction, miss, ace, snv1, serve_number)

        else:
            print("error, first serve not found in: ", o1, "or", c1, s1)

    server.first_serve_percent = (server.made_first_serves / server.total_first_serves) * 100
    server.second_serve_percent = (server.made_second_serves / server.total_second_serves) * 100


class Point:
    def __init__(self, point_number, svr, returner, first, second, winner):
        self.point_number = point_number
        self.svr = svr
        self.returner = returner
        self.first = first
        self.second = second
        self.winner = winner

    # 5b2f1s3w#
    # svr = 1
    # parse serve
    # adds serve to player 1
    # need to start at b
    # player 2 hits a backhand down the middle
    # player 1 hits a forehand to the duece side
    # player 2 hits a slice to the ad side and misses wide - forced

    def parse_point(self, point, server, returner, serve_code, shot_code, error_code):
        handle_serve(self, point, serve_code, shot_code, error_code, server)
        print(point)
