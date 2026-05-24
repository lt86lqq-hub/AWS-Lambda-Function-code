import json
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("smart_cup")


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=decimal_default),
    }


def lambda_handler(event, context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

        if method == "OPTIONS":
            return response(200, {"message": "OK"})

        # ---------- POST: manual drink record ----------
        if method == "POST":
            body = event.get("body") or "{}"
            data = json.loads(body) if isinstance(body, str) else body

            item = {
                "cup_ID": data.get("cup_ID", "cup_01"),
                "timestamp": data.get("timestamp"),
                "user_id": data.get("user_id"),
                "user_name": data.get("user_name", ""),
                "device_id": data.get("device_id", "Manual"),
                "event_type": data.get("event_type", "drink"),
                "event_valid": data.get("event_valid", True),
                "delta_ml": Decimal(str(data.get("delta_ml", 0))),
            }

            if not item["cup_ID"] or not item["timestamp"] or not item["user_id"]:
                return response(400, {
                    "error": "Missing required fields: cup_ID, timestamp, user_id"
                })

            table.put_item(Item=item)

            return response(200, {
                "message": "Drink record added successfully",
                "item": item
            })

        # ---------- GET: read records ----------
        params = event.get("queryStringParameters") or {}

        cup_id = params.get("cup_ID") or params.get("cup_id") or "cup_01"
        user_id = params.get("user_id")
        social = params.get("social") == "true"

        items = []
        last_key = None

        while True:
            if social:
                query_kwargs = {}
                if last_key:
                    query_kwargs["ExclusiveStartKey"] = last_key
                result = table.scan(**query_kwargs)
            else:
                query_kwargs = {
                    "KeyConditionExpression": Key("cup_ID").eq(cup_id),
                    "ScanIndexForward": False,
                }
                if last_key:
                    query_kwargs["ExclusiveStartKey"] = last_key
                result = table.query(**query_kwargs)

            items.extend(result.get("Items", []))

            last_key = result.get("LastEvaluatedKey")
            if not last_key:
                break

        if user_id and not social:
            items = [
                item for item in items
                if item.get("user_id") == user_id
            ]

        # 不判断 event_valid，直接使用所有读取到的数据
        valid_items = items

        drink_items = [
            item for item in valid_items
            if item.get("event_type") in ["drink", "drink_event"]
        ]

        reminder_items = [
            item for item in valid_items
            if item.get("event_type") == "reminder"
        ]

        total_ml = sum(
            float(item.get("delta_ml", 0) or 0)
            for item in drink_items
        )

        return response(200, {
            "cup_ID": cup_id,
            "user_id": user_id,
            "social": social,
            "total_ml": total_ml,
            "records": valid_items,
            "drink_records": drink_items,
            "reminder_records": reminder_items,
            "count": len(valid_items),
        })

    except Exception as e:
        return response(500, {
            "error": str(e)
        })