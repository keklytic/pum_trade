# PUMP TRADE DUNE

## Deployment

To deploy this repo to lambda, run the following code

```sh

# install dependencies
docker run --rm \                                                                                                                                                            
    --platform linux/x86_64 \                                                                                                                                                  
    --entrypoint bash \                                                                                                                                                        
    -v "$(pwd):/var/task" \
    -w /var/task \                                                                                                                                                             
    public.ecr.aws/lambda/python:3.11 \                                                                                                                                        
    -c "pip install -r requirements.txt -t /var/task/lambda_package/"
                                                                                                                                                                              # copy existing code to directory
  cp dune_result.py lambda_handler.py gsheet_credentials.json lambda_package/                                                                                                
                                                                                                                                                                              # zip the files for lambda upload
  cd lambda_package && zip -r ../lambda_deployment.zip . && cd ..             
```

## Running on locals

To run the script on locals:

1. install dependencies:

```sh
pip install -r requirements.txt
```

2. Set dune api key on `test_local.py`

3. run :
```sh
  GOOGLE_CREDS_JSON=$(cat /Users/rftahir/Works/Wallet/pum_trade_ori/gsheet_credentials.json) python3 dune_result.py
```