import requests
import re
import json
import logging
from criteo.vault.config.helpers import *
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64
import struct


def _b64toi(s: str):
    s_ascii = (s + "==").encode('ascii')
    decoded = base64.urlsafe_b64decode(bytes(s_ascii))
    return int(''.join(["%02x" % byte for byte in struct.unpack("%sB" % len(decoded), decoded)]), 16)


def get_issuers_keys(env: str):
    domain = "https://sso-jwk-http.par.{env}.crto.in/".format(env=env)
    main_page = requests.get(domain)
    if main_page.status_code not in [200, 204]:
        raise Exception("Call to {url} failed with status code {code}. Content: {content}".format(url=domain, code=main_page.status_code, content=main_page.content))
    criteo_issuers = list(set(re.findall(r'criteo-[a-z-]+', main_page.content.decode('utf-8'))))
    pub_keys = []
    for iss_name in criteo_issuers:
        if iss_name == "criteo-local":
            # We don't trust criteo-local issuer. This would allow too much disclosure
            continue
        iss_res = requests.get(domain + iss_name + ".jwk.json")
        keys = []
        if iss_res.status_code not in [200, 204]:
            raise Exception("Call to {url} failed with status code {code}. Content: {content}".format(url=iss_res.url, code=iss_res.status_code, content=iss_res.content))
        try:
            keys = iss_res.json()['keys']
        except json.JSONDecodeError as e:
            logging.error("issuer {}: Error while decoding json. Content is ".format(iss_name) + iss_res.content)
            raise e
        except KeyError as e:
            logging.error("issuer {}: \"keys\" is not present in the json. Content is".format(iss_name) + iss_res.content)
        for jwk in keys:
            exp = _b64toi(jwk['e'])
            mod = _b64toi(jwk['n'])
            nums = RSAPublicNumbers(exp, mod)
            pub = nums.public_key(default_backend())
            pem = pub.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
            logging.debug("issuer {}: found a public key: ".format(iss_name) + str(pem))
            pub_keys.append(pem.decode("utf-8"))
    return pub_keys


def generate_jwt_config(config_dir, ctx):
    keys = get_issuers_keys(ctx['env'])
    if len(keys) < 1:
        raise Exception("Unknown error while fetching the public keys")
    logging.info("generating the config file for JWT backend")
    write_file(config_dir + "/auth/jwt/config.json", json.dumps({
        "jwt_validation_pubkeys": keys
    }))
