import json
import lambda_dispatcher

fake_event = {
  "httpMethod": "POST",
  "body": json.dumps({
      "ca": "your_token_address_here",
      "wallets": [
          "wallet_address_1",
          "wallet_address_2"
      ]
  })
}

result = lambda_dispatcher.lambda_handler(fake_event, None)
print(json.dumps(result, indent=2))
