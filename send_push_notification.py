import json
import urllib3
import boto3

http = urllib3.PoolManager()
dynamodb = boto3.resource("dynamodb")

users_table = dynamodb.Table("smart_cup_users")


def get_value(field):
    if "S" in field:
        return field["S"]
    if "N" in field:
        return float(field["N"])
    if "BOOL" in field:
        return field["BOOL"]
    if "NULL" in field:
        return None
    return None


def send_expo_push(token, title, body):
    message = {
        "to": token,
        "sound": "default",
        "title": title,
        "body": body,
        "data": {
            "screen": "HomeReminder"
        }
    }

    response = http.request(
        "POST",
        "https://exp.host/--/api/v2/push/send",
        body=json.dumps(message),
        headers={"Content-Type": "application/json"}
    )

    return response.data.decode("utf-8")


def lambda_handler(event, context):
    print("FULL EVENT:", json.dumps(event))
    results = []

    for record in event.get("Records", []):
        if record.get("eventName") not in ["INSERT", "MODIFY"]:
            continue

        new_image = record.get("dynamodb", {}).get("NewImage", {})

        event_type = get_value(new_image.get("event_type", {}))
        event_valid = get_value(new_image.get("event_valid", {}))
        user_id = get_value(new_image.get("user_id", {}))
        cup_id = get_value(new_image.get("cup_ID", {}))

        reason = get_value(new_image.get("reminder_reason", {}))
        low_intake = get_value(new_image.get("low_intake_reminder", {}))
        no_drink = get_value(new_image.get("no_drink_reminder", {}))

        if event_type != "reminder":
            continue

       # if event_valid is not True:
         #   continue

        if not user_id:
            continue

        user_response = users_table.get_item(
            Key={
                "user_id": user_id
            }
        )

        user_item = user_response.get("Item")
        print("USER ITEM:", user_item)

        if not user_item:
            results.append(f"No user found for {user_id}")
            continue

        token = user_item.get("expo_push_token")
        print("TOKEN:", token)

        if not token:
            results.append(f"No token found for {user_id}")
            continue

        title = "Smart Cup Reminder 💧"

        if reason:
            body = reason
        elif no_drink:
            body = "You haven't had water for 60 minutes. Time to hydrate 💧"
        elif low_intake:
            body = "Your water intake is below target. Please drink some water 💧"
        else:
            body = "Time to drink water 💧"

        push_result = send_expo_push(token, title, body)

        print("Expo push result:", push_result)
        print("TITLE:", title)
        print("BODY:", body)      


        results.append({
            "user_id": user_id,
            "cup_ID": cup_id,
            "event_type": event_type,
            "body": body,
            "push_result": push_result
        })
        
    print("FINAL RESULTS:", results)

    return {
        "statusCode": 200,
        "body": json.dumps(results)
    }