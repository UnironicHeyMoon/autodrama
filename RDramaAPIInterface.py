import time
import requests
'''
Wrapper around the RDRama API
'''
class RDramaAPIInterface:
    def __init__(self, authorization_token, site, sleep : float, https: bool = True) -> None:
        self.headers={"Authorization": authorization_token}
        self.site = site
        self.protocol = "https" if https else "http"
        self.sleep = sleep

    def make_post(self, title, submission_url, body):
        url=f"{self.protocol}://{self.site}/submit"
        return self.post(url, data={'title' : title, 'url': submission_url, 'body': body})

    '''
    Sends a message to a user.
    '''
    def send_message(self, username, message):
        url=f"{self.protocol}://{self.site}/@{username}/message"
        return self.post(url, data={'message':message})

    '''
    Replies to the comment with the given id.
    '''
    def reply_to_comment(self,parent_fullname, parent_submission, message):
        url=f"{self.protocol}://{self.site}/comment"
        return self.post(url, data={
            'parent_fullname':parent_fullname,
            'submission': parent_submission,
            "body": message
            })

    '''
    Replies to the comment with the given id.
    '''
    def reply_to_comment_easy(self,comment_id, parent_submission, message):
        return self.reply_to_comment(f"t3_{comment_id}", parent_submission, message)

    '''
    Gets "all" comments. TODO: Probably need to add pagination support if I want to actually use this
    '''
    def get_comments(self):
        url=f"{self.protocol}://{self.site}/comments"
        return self.get(url)

    '''
    Calls the notifications endpoint
    '''
    def get_notifications(self, page : int):
        url=f"{self.protocol}://{self.site}/notifications?page={page}"
        return self.get(url)

    def reply_to_direct_message(self, message_id : int, message : str):
        url=f"{self.protocol}://{self.site}/reply"
        return self.post(url, data = {
            'parent_id' : message_id,
            'body': message
        }, allowed_failures=[500]) #There is a bug (probably) with the site that causes 500 errors to be sent when doing this via json. TODO: Ask Aevann why

    def get_comment(self, id):
        url=f"{self.protocol}://{self.site}/comment/{id}"
        return self.get(url)

    def has_url_been_posted(self, the_url):
        url=f"{self.protocol}://{self.site}/is_repost"
        return self.post(url, {'url': the_url})['permalink'] != ''

    '''
    I have no clue what this is supposed to do, lol.
    '''
    def clear_notifications(self):
        url=f"{self.protocol}://{self.site}/clear"
        return self.post(url, headers=self.headers)

    def give_coins(self, user, amount):
        url=f"{self.protocol}://{self.site}/@{user}/transfer_coins"
        return self.post(url, data={'amount':amount})

    def get(self, url, allowed_failures = []):
        print(f"[rdrama_api] sleeping for {self.sleep}")
        time.sleep(self.sleep)
        print(f"[rdrama_api] Awake")
        response = requests.get(url, headers=self.headers)
        print(f"GET {url} ({response.status_code}) {response.json()}")
        if (response.status_code != 200 and response.status_code not in allowed_failures):
            raise BaseException(f"GET {url} ({response.status_code}) {response.json()}")
        else:
            return response.json()
    
    def post(self, url, data, allowed_failures = []):
        print(f"[rdrama_api] sleeping for {self.sleep}")
        time.sleep(self.sleep)
        print(f"[rdrama_api] Awake")
        response = requests.post(url, headers=self.headers, data=data)
        print(f"POST {url} ({response.status_code}) {data} => {response.json()}")
        if (response.status_code != 200  and response.status_code not in allowed_failures):
            raise BaseException(f"POST {url} ({response.status_code}) {data} => {response.json()}")
        else:
            return response.json()