# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from urllib.parse import urlencode, unquote

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url_to_form
from frappe.utils.file_manager import get_file_path


class LinkedIn(Document):
    @frappe.whitelist()
    def get_authorization_url(self):
        params = urlencode(
            {
                "response_type": "code",
                "client_id": self.consumer_key,
                "redirect_uri": "{0}/api/method/social_media.social_media.doctype.linkedin.linkedin.callback?".format(
                    frappe.utils.get_url()
                ),
                "scope": "profile email openid w_member_social",
            }
        )

        url = "https://www.linkedin.com/oauth/v2/authorization?{}".format(params)

        return url

    def get_access_token(self, code):
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.consumer_key,
            "client_secret": self.get_password(fieldname="consumer_secret"),
            "redirect_uri": "{0}/api/method/social_media.social_media.doctype.linkedin.linkedin.callback?".format(
                frappe.utils.get_url()
            ),
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = self.http_post(url=url, data=body, headers=headers)
        response = frappe.parse_json(response.content.decode())
        self.db_set("access_token", response["access_token"])

    def get_member_profile(self):
        response = requests.get(
            url="https://api.linkedin.com/v2/userinfo", headers=self.get_headers()
        )
        parsed_response = frappe.parse_json(response.content.decode())

        frappe.db.set_value(
            self.doctype,
            self.name,
            {
                "person_urn": parsed_response["sub"],
                "account_name": parsed_response["name"],
                "session_status": "Active",
            },
        )

        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = get_url_to_form("LinkedIn", "LinkedIn")

    def post(self, text, title, docname, media=None, video=None):

        if not media and not video:
            return self.post_text(text, title, docname)
        elif media:
            media_id = self.upload_image(media)

            if media_id:
                return self.post_text(text, title, docname, media_id=media_id)

            else:
                self.log_error("LinkedIn: Failed to upload media")
        elif video:
            video_id = self.upload_image(media, video)
            if video_id:
                return self.post_text(text, title, docname, video_id=video_id)
            else:
                self.log_error("LinkedIn: Failed to upload media")

    def upload_image(self, media=None, video=None):
        if media:
            media_path = get_file_path(media)
        elif video:
            video_path = get_file_path(video)

        # LinkedIn API endpoint for registering the upload
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"

        body = {
            "registerUploadRequest": {
                "owner": "urn:li:person:{0}".format(self.person_urn),
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        body["registerUploadRequest"]["recipes"] = []
        if media:
            body["registerUploadRequest"]["recipes"].append(
                "urn:li:digitalmediaRecipe:feedshare-image"
            )
        elif video:
            body["registerUploadRequest"]["recipes"].append(
                "urn:li:digitalmediaRecipe:feedshare-video"
            )

        headers = self.get_headers()

        response = self.http_post(url=register_url, body=body, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            asset = response_data["value"]["asset"]

            upload_url = response_data["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]

            if media:
                headers["Content-Type"] = "image/jpeg"
                response = self.http_post(
                    upload_url, headers=headers, data=open(media_path, "rb")
                )
            elif video:
                headers["Content-Type"] = "video/mp4"
                response = self.http_post(
                    upload_url, headers=headers, data=open(video_path, "rb")
                )

            if response.status_code < 200 or response.status_code > 299:
                frappe.throw(
                    _("Error While Uploading Image"),
                    title="{0} {1}".format(response.status_code, response.reason),
                )
                return None

            return asset
        return None

    def post_text(self, text, title, docname, media_id=None, video_id=None):
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = self.get_headers()
        headers["X-Restli-Protocol-Version"] = "2.0.0"
        headers["Content-Type"] = "application/json; charset=UTF-8"
        if media_id:
            body = {
                "author": "urn:li:person:{0}".format(self.person_urn),
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "media": media_id,
                                "title": {"text": title},
                            }
                        ],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
        elif video_id:
            body = {
                "author": "urn:li:person:{0}".format(self.person_urn),
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "VIDEO",
                        "media": [
                            {
                                "status": "READY",
                                "media": video_id,
                                "title": {"text": title},
                            }
                        ],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }

        else:
            body = {
                "author": "urn:li:person:{0}".format(self.person_urn),
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }

        response = self.http_post(docname=docname, url=url, headers=headers, body=body)
        frappe.msgprint("LinkedIn Post Share Successfully ", indicator="green")
        return response

    def http_post(self, url, docname=None, headers=None, body=None, data=None):
        try:
            # Send POST request to the specified URL
            response = requests.post(url=url, json=body, data=data, headers=headers)

            if response.status_code in [201]:
                urn_post = response.headers.get("Location")
                if urn_post:
                    urn_id = urn_post.split("/")
                    post_id = unquote(urn_id[-1])
                    frappe.db.set_value("linkedin Post", docname, "post_id", post_id)
                    self.save()

            elif response.status_code not in [201, 200]:
                raise requests.exceptions.HTTPError(
                    f"Unexpected status code: {response.status_code}"
                )

        except Exception as e:
            # Handle any exceptions that occur during the process
            self.api_error(response)

        return response

    def get_headers(self):
        return {"Authorization": "Bearer {}".format(self.access_token)}

    def get_reference_url(self, text):
        import re

        regex_url = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        urls = re.findall(regex_url, text)
        if urls:
            return urls[0]

    def delete_post(self, post_id):
        try:
            response = requests.delete(
                url="https://api.linkedin.com/v2/ugcPosts/{0}".format(post_id),
                headers=self.get_headers(),
            )

            if response.status_code != 204 and response.content:
                self.api_error(response)
            else:
                frappe.msgprint("LinkedIn Post Delete successfully ", indicator="green")
        except Exception as e:
            self.api_error(response)

    def get_post(self, post_id):
        url = "https://api.linkedin.com/v2/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:{0}&shares[0]=urn:li:share:{1}".format(
            self.company_id, post_id
        )

        try:
            response = requests.get(url=url, headers=self.get_headers())
            if response.status_code != 200:
                raise

        except Exception:
            self.api_error(response)

        response = frappe.parse_json(response.content.decode())
        if len(response.elements):
            return response.elements[0]

        return None

    def api_error(self, response):
        content = frappe.parse_json(response.content.decode())
        # Adjusted indentation here

        if response.status_code == 401:
            self.db_set("session_status", "Expired")
            frappe.db.commit()
            frappe.throw(content["message"], title=_("LinkedIn Error - Unauthorized"))
        elif response.status_code == 403:
            frappe.msgprint(_("You didn't have permission to access this API"))
            frappe.throw(content["message"], title=_("LinkedIn Error - Access Denied"))
        else:
            frappe.throw(response.reason, title=response.status_code)


@frappe.whitelist(allow_guest=True)
def callback(code=None, error=None, error_description=None):
    if not error:
        linkedin_settings = frappe.get_doc("LinkedIn")
        linkedin_settings.get_access_token(code)
        linkedin_settings.get_member_profile()
        frappe.db.commit()
    else:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = get_url_to_form("LinkedIn", "LinkedIn")


@frappe.whitelist(allow_guest=True)
def post(text, title, docname, media=None, video=None):
    linkedin_settings = frappe.get_doc("LinkedIn")
    linkedin_settings.post(text, title, docname, media, video)


@frappe.whitelist(allow_guest=True)
def delete(post_id):
    linkedin_settings = frappe.get_doc("LinkedIn")
    linkedin_settings.delete_post(post_id)
