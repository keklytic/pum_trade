import json                                               
import lambda_handler
                      
fake_event = {                                                                                                                                                               
  "httpMethod": "POST",
  "body": json.dumps({                                                                                                                                                     
      "dune_api_key": "your_dune_api_key_here"          
  })                                          
}     
  
result = lambda_handler.lambda_handler(fake_event, None)
print(json.dumps(result, indent=2))    