"""Pure queue/routing rules. Network, mailbox and Drive adapters are separate.

No credentials, addresses or personal contacts belong in this module.
"""
from datetime import datetime, timezone
from email.message import EmailMessage
from email import policy
from pathlib import PurePosixPath
from uuid import UUID
import json
import re

VERSION = '1.0.0'
PROTOCOL = 'corporate-helper/1'

def guid(value):
    if not isinstance(value, str):
        raise ValueError('GUID string required')
    result = str(UUID(value))
    if result != value.lower():
        raise ValueError('Canonical GUID required')
    return result

def single_line(value):
    if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00'):
        raise ValueError('Nonempty single line required')
    return value

def validate_request(packet, authenticated_worker):
    fields = {'protocol','request_id','tool','arguments'}
    if not isinstance(packet,dict) or set(packet) != fields:
        raise ValueError('Unexpected request fields')
    if packet['protocol'] != PROTOCOL or packet['tool'] != 'sms.enqueue':
        raise ValueError('Unsupported protocol or tool')
    request_id = guid(packet['request_id'])
    worker = guid(authenticated_worker)  # From the paired principal, never page claims.
    args = packet['arguments']
    if not isinstance(args,dict) or set(args) != {'recipient','text'}:
        raise ValueError('Unexpected SMS arguments')
    recipient = single_line(args['recipient'])
    text = args['text']
    if not isinstance(text,str) or not text.strip() or len(text)>10000 or '\x00' in text:
        raise ValueError('Invalid message text')
    return {'request_id':request_id,'worker_guid':worker,'recipient':recipient,'text':text}

def queue_name(when, direction, sender_guid):
    if when.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    if direction not in ('in','out'):
        raise ValueError('Direction required')
    # Microseconds preserve UTC lexical sorting; request ID remains authoritative for dedup.
    stamp=when.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    return f'{stamp}.({direction}).{guid(sender_guid)}.txt'

def mail_record(message, when, destination_email, reply_domain):
    """Prepare an outbound .txt email. Does not send or write anything."""
    worker=guid(message['worker_guid']); request_id=guid(message['request_id'])
    address=single_line(destination_email); domain=single_line(reply_domain)
    if not re.fullmatch(r'[A-Za-z0-9.-]+\.[A-Za-z]{2,}',domain):
        raise ValueError('Invalid reply domain')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',address):
        raise ValueError('Invalid recipient email')
    if when.tzinfo is None: raise ValueError('Timezone-aware timestamp required')
    mail=EmailMessage(policy=policy.SMTP)
    mail['To']=address
    mail['Reply-To']=f'{worker}.sms@{domain}'
    mail['Message-ID']=f'<{request_id}@{domain}>'
    mail['Subject']='Message notification'
    mail['X-Worker-GUID']=worker
    mail['X-Request-ID']=request_id
    mail['X-Queue-Direction']='out'
    mail['X-Queue-State']='QUEUED'
    mail['X-Queue-Created-UTC']=when.astimezone(timezone.utc).isoformat(timespec='microseconds')
    mail.set_content(f"Worker-GUID: {worker}\nRequest-ID: {request_id}\n\n{message['text']}")
    return queue_name(when,'out',worker),mail.as_bytes()

def requires_objectives(filename, parent_id, queue_folder_id):
    """Exempt all _readme.txt and direct queue records by stable folder ID."""
    if PurePosixPath(filename).name.lower() == '_readme.txt': return False
    if queue_folder_id and parent_id == queue_folder_id: return False
    return True

def handoff_decision(local_identity, master_identity, local_release, master_release,
                     authenticated_master, operation_state, fallback_lease=False):
    """Caller obtains a fenced lease from shared authority before fallback writes.

    release = exact package version + build/source digest; hostname is not identity.
    operation_state: NEW / CONFIRMED / NOT_ACCEPTED / UNKNOWN.
    """
    if authenticated_master and local_identity == master_identity:
        return 'MASTER_EXECUTE'
    if operation_state == 'CONFIRMED': return 'RETURN_RECEIPT'
    if operation_state == 'UNKNOWN': return 'RECONCILE_ONLY'
    if authenticated_master: return 'HANDOFF_TO_MASTER'
    if local_release == master_release and fallback_lease and operation_state in ('NEW','NOT_ACCEPTED'):
        return 'FALLBACK_EXECUTE'
    return 'QUEUE_PENDING'

def inbound_route(reply_address, reply_domain, routing_table):
    """Recognize worker alias; authentication and sender authorization precede this."""
    single_line(reply_address)
    suffix='.sms@'+reply_domain
    if not reply_address.lower().endswith(suffix.lower()):
        raise ValueError('Wrong reply domain')
    worker=guid(reply_address[:-len(suffix)])
    if worker not in routing_table: raise ValueError('Unknown reply worker')
    return {'worker_guid':worker,'route':routing_table[worker]}
