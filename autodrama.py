TEST_MODE = True

from re import sub
from time import sleep
from typing import Tuple
import praw
from praw.models import Comment, Submission
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from psaw import PushshiftAPI
from os.path import exists, join, realpath, split

from RDramaAPIInterface import RDramaAPIInterface

def get_real_filename(filename : str):
    path_to_script = realpath(__file__)
    path_to_script_directory, _ = split(path_to_script)
    return join(path_to_script_directory, filename)

with open(get_real_filename("id")) as f:
    client_id = f.read()
with open(get_real_filename("secret")) as f:
    client_secret = f.read()
with open(get_real_filename("user_agent")) as f:
    user_agent = f.read()

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent
)

pushshift_api = PushshiftAPI(reddit)

def get_based_submissions(subreddit, time_frame, limit):
    subscriber_cache = {}

    submissions = []
    most_based_submission = None
    most_based_score = 0
    most_relatively_based_submission = None
    most_relatively_based_score = 0
    for submission in reddit.subreddit(subreddit).controversial(time_frame, limit=limit):
        try:
            basedness = (1-submission.upvote_ratio)*submission.num_comments
            if (submission.author.name == "AutoModerator" or "comment" in submission.title.lower()):
                continue
            if (submission.subreddit not in subscriber_cache):
                subscriber_cache[submission.subreddit] = submission.subreddit.subscribers
            relative_basedness = ((basedness/subscriber_cache[submission.subreddit]))*100000
            if (basedness > most_based_score):
                most_based_score = basedness
                most_based_submission = submission
            if (relative_basedness > most_relatively_based_score):
                most_relatively_based_score = relative_basedness
                most_relatively_based_submission = submission
            submissions.append((basedness, relative_basedness, submission))
            print(f"(B: {basedness} RB: {relative_basedness}){submission.title}")
        except:
            print(f"Error while processing {submission}")

    return submissions

def analyze_comments(submission : 'Submission'):
    print(f"[{submission.id}]Retrieving Comments")
    comments = pushshift_api.search_comments(subreddit=submission.subreddit.display_name, link_id=submission.id)
    print(f"[{submission.id}]Creating Network")
    comment_map = {i.id:i for i in list(comments)}
    child_map = {}
    for comment in comment_map.values():
        try:
            parent_id = comment.parent_id[3:]
            if (parent_id not in child_map):
                child_map[parent_id] = []
            child_map[parent_id].append(comment)
        except:
            print(f"Error matching {comment} to its parent.")

    sid_obj = SentimentIntensityAnalyzer()
    print(f"[{submission.id}]Classifying Comments")
    user_to_total_anger = {}
    ranked_comments = []
    angry_comments = []
    for comment in comment_map.values():
        try:
            comment_info = {
                'comment' : comment
            }
            if (comment.body == '[deleted]' or comment.author == None):
                continue
            if ("t1" in comment.parent_id[0:2]): #Not a parent comment
                parent = comment_map[comment.parent_id[3:]]
                comment_info['parent'] = parent
                parent_score = parent.score
                if (comment.id in child_map):
                    child_scores = [i.score for i in child_map[comment.id] if isinstance(i, Comment)]
                else:
                    child_scores = []
                if len(child_scores) > 0: #More than one child - not sure how to handle the no child case
                    average_child_score = sum(child_scores)/len(child_scores)
                    if (average_child_score > 0 and parent_score > 0):
                        comment_score = comment.score
                        if (comment_score >= average_child_score and comment_score <= parent_score):
                            pass
                        else:
                            basedness = average_child_score - comment_score
                            ranked_comments.append((basedness, comment_info))
            else:
                #A parent comment
                comment_info['parent'] = None
                if (comment.id in child_map):
                    child_scores = [i.score for i in child_map[comment.id] if isinstance(i, Comment)]
                else:
                    child_scores = []
                if len(child_scores) > 0: #More than one child - not sure how to handle the no child case
                    average_child_score = sum(child_scores)/len(child_scores)
                    comment_score = comment.score
                    if (comment_score >= average_child_score):
                        pass
                    else:
                        basedness = average_child_score - comment_score
                        ranked_comments.append((basedness, comment_info))
            # Add to angriness
            score = sid_obj.polarity_scores(comment.body)['compound']
            if score < -0.5:
                angry_comments.append((sid_obj.polarity_scores(comment.body)['compound'], comment_info))
            
            if comment.author not in user_to_total_anger:
                user_to_total_anger[comment.author] = 0.0
            user_to_total_anger[comment.author]+=score
        except Exception as e:
            print(f"Error while processing {comment}: {e}")

    print(f"[{submission.id}]Done")
    ranked_comments.sort(reverse=True, key= lambda a : a[0])
    angry_comments.sort(key=lambda a:a[0])
    lolcows = [(v, k) for k, v in user_to_total_anger.items()]
    lolcows.sort(key=lambda a:a[0])
    return {
        'based' : ranked_comments,
        'angry': angry_comments,
        'lolcows': lolcows
    }
#get_based_submissions("all", "hour", 25, True)

def generate_comment_display_section(submissions : 'Tuple[float, Submission]', section_title, detail_display, number_to_show, show_details = True, detail_func = lambda a : a, max_len = 1000 ):
    markdown_lines = []
    if len(submissions) != 0:
        markdown_lines.append(f"## {section_title}")
        for comment_info in submissions[:number_to_show]:
            attribute = comment_info[0]
            parent = comment_info[1]['parent']
            comment = comment_info[1]['comment']
            if (show_details):
                markdown_lines.append(f"{detail_display}: {detail_func(attribute)}")
            comment_indent = ""

            if (parent != None):
                parent_body = parent.body.replace("\n", "")
                if len(parent_body) > max_len:
                    parent_body = parent_body[0:max_len-3] + "..."
                markdown_lines.append(f"> {parent_body} ({parent.score})")
                comment_indent = ">>"
            else:
                comment_indent = ">"

            comment_body = comment.body.replace("\n", "")
            if len(comment_body) > max_len:
                comment_body = comment_body[0:max_len-3] + "..."
            markdown_lines.append(f"{comment_indent} [{comment_body}](https://reddit.com{comment.permalink}) ({comment.score})")
    return markdown_lines

def comment_basedness_score_string(basedness):
    score = 0
    if basedness > 1000:
        score = 5
    elif basedness > 500:
        score = 4
    elif basedness > 100:
        score = 3
    elif basedness > 50:
        score = 2
    elif basedness > 10:
        score = 1
    else:
        score = 0
    return get_score_string(score, "🔥", "🔘")

def angriness_score_string(angriness):
    score = 0
    if angriness < -0.95:
        score = 5
    elif angriness < -0.9:
        score = 4
    elif angriness < -0.85:
        score = 3
    elif angriness < -0.75:
        score = 2
    elif angriness < -0.6:
        score = 1
    else:
        score = 0
    
    return get_score_string(score, "😡", "🔘")

def generate_submission_report(submission : 'Submission', absolute: bool):
    markdown_lines = []
    comment_analysis_results = analyze_comments(submission)
    basedness_display_func = lambda a : get_comment_basedness_out_of_five(a, absolute)
    markdown_lines.extend(generate_comment_display_section(comment_analysis_results['based'], "Most Based Comments", "Basedness", 3, detail_func=basedness_display_func))
    markdown_lines.extend(generate_comment_display_section(comment_analysis_results['angry'], "Angriest Comments", "Angriness", 3, detail_func=angriness_score_string))
    biggest_lolcow_info = comment_analysis_results['lolcows'][0]
    biggest_lolcow_score = biggest_lolcow_info[0]
    biggest_lolcow = biggest_lolcow_info[1]
    markdown_lines.append(f"# Biggest lolcow")
    lolcow_score_string = get_score_string(-1*biggest_lolcow_score, "🐮", "🔘")
    markdown_lines.append(f"/u/{biggest_lolcow.name} {lolcow_score_string}")
    markdown_lines.append("*:marppy: autodrama: automating away the jobs of dramautists. :marseycapitalistmanlet: Ping HeyMoon if there are any problems or you have a suggestion :marseyjamming:*")
    return "\n\n".join(markdown_lines)

def create_file_report(submission : 'Submission'):
    submission_name = submission.title
    print(f"Generating submission for https://reddit.com{submission.permalink}")
    filename = "".join([i.lower() for i in submission_name if i.lower() in "abcdefghijklmnopqrstuvwxyz "])[:30].replace(" ", "_") + "_" + submission.subreddit.name + ".md"
    submission_report = generate_submission_report(submission)
    print(submission_report)
    with open(filename, "wb") as f:
        f.write(submission_report.encode("utf-8"))

def create_file_reports_for_list_of_submissions(submissions : 'list[Tuple[float, float, Submission]]'):
    for i in submissions:
        try:
            submission = i[2]
            create_file_report(submission)
        except Exception as e:
            print(f"Yikes, had a bit of a fucky wucky: {e}")

def get_basedness_score_out_of_five(basedness : int) -> int:
    if basedness > 10000:
        return 5
    elif basedness > 5000:
        return 4
    elif basedness > 1000:
        return 3
    elif basedness > 100:
        return 2
    elif basedness > 10:
        return 1
    else:
        return 0

def get_comment_basedness_out_of_five(basedness: int, absolute : bool):
    if (absolute):
        if basedness > 1000:
            score = 5
        elif basedness > 500:
            score = 4
        elif basedness > 100:
            score = 3
        elif basedness > 50:
            score = 2
        elif basedness > 10:
            score = 1
        else:
            score = 0
    else:
        if basedness > 100:
            score = 5
        elif basedness > 50:
            score = 4
        elif basedness > 10:
            score = 3
        elif basedness > 5:
            score = 2
        elif basedness > 1:
            score = 1
        else:
            score = 0
    return get_score_string(score, "🔥", "🔘")

def get_score_string(score: int, filled_emoji, empty_emoji) -> str:
    return "".join([filled_emoji if ((i+1) <= score) else empty_emoji for i in range(5)])

def create_rdrama_report(rdrama : RDramaAPIInterface, submission : 'Submission', basedness: int, absolute_basedness: bool):
    score = get_basedness_score_out_of_five(basedness)
    score_string = get_score_string(score, "🔥" if absolute_basedness else "🤓", "🔘")
    title = f"[{score_string}] {submission.title}"
    url = f"https://reddit.com{submission.permalink}"
    body = generate_submission_report(submission, absolute_basedness)
    if len(body) > 20000:
        body = body[0:19997] + "..."
    try:
        rdrama.make_post(title, url, body)
    except Exception as e:
        print(f"Yikes, a fucky wucky occured! {e}")

def get_first_unposted(rdrama : RDramaAPIInterface, submissions : 'list[Submission]'):
    for submission in submissions:
        if (not rdrama.has_url_been_posted(f"https://www.reddit.com{submission.permalink}")):
            return submission
    return None

def daily_drama_post(rdrama : RDramaAPIInterface):
    print("Performing Daily Drama Post!")
    based_submissions = get_based_submissions("all", "day", 150)
    print("Posting the most relatively based submission for the day...")
    based_submissions.sort(reverse=True, key = lambda a : a[1]) #Sort by relative basedness
    most_relatively_based_submission = get_first_unposted(rdrama, [i[2] for i in based_submissions])
    create_rdrama_report(rdrama, most_relatively_based_submission, based_submissions[0][1], False)
    print("Posting the most based submission for the day...")
    based_submissions.sort(reverse=True, key = lambda a : a[0]) #Sort by basedness
    most_absolutely_based_submission = get_first_unposted(rdrama, [i[2] for i in based_submissions])
    create_rdrama_report(rdrama, most_absolutely_based_submission, based_submissions[0][0], True)
    print("Done!")

TEST_AUTH_TOKEN = "jU_k7alzoqfogYqQgcPJ3vIWILiDtI7UWdMTmKbvuttMih-YbhRCs8B3BBCRSKkdSJ0w_JfzJn2YBkdDEw5DIf3UXb3vGTRvLB_9BQ9zBiTz9opp3MFGSudH_s_C7keq" #todo - parameterize
if TEST_MODE:
    website = "localhost"
    auth = TEST_AUTH_TOKEN
    https = False
    timeout = 1
else:
    website = "rdrama.net"
    with open(get_real_filename("rdrama_auth_token"), "r") as f:
        auth = f.read()
    https = True
    timeout = 10
rdrama = RDramaAPIInterface(auth, website, timeout, https=https)

daily_drama_post(rdrama)
