#! /usr/bin/env python3

# See more
# https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/compute/api/create_instance.py

import argparse
import os
import time

import googleapiclient.discovery

def instance_ip(compute, project, zone, instance):
    r = compute.instances().get(project=project, zone=zone, instance=instance).execute()
    for n in r["networkInterfaces"]:
        for x in n["accessConfigs"]:
            if "natIP" in x:
                return x["natIP"]
    return None  

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    for r in result['items']:
        #print(r)
        s = f" - {r['name']}, {r['status']}, {r['machineType'].split('/')[-1]}"
        if "guestAccelerators" in r:
            for x in r["guestAccelerators"]:
                s += f", {x['acceleratorType'].split('/')[-1].split('-')[-1]}*{x['acceleratorCount']}"
        for n in r["networkInterfaces"]:
            for x in n["accessConfigs"]:
                if "natIP" in x:
                    s += f", {x['natIP']}"
        print(s)

def wait_for_operation(compute, project, zone, operation):
    print('Waiting for operation to finish...')
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)

def start_instance(compute, project, zone, instance):
    op = compute.instances().start(
        project=project,
        zone=zone,
        instance=instance).execute()
    wait_for_operation(compute, project, zone, op['name'])

def stop_instance(compute, project, zone, instance):
    op = compute.instances().stop(
        project=project,
        zone=zone,
        instance=instance).execute()
    wait_for_operation(compute, project, zone, op['name'])

def set_gpu(compute, project, zone, instance, gpu):
    gpu_to_fullname = {
        "v100": "nvidia-tesla-v100",
        "t4": "nvidia-tesla-t4",
        "none": None,
    }
    gpu = gpu_to_fullname[gpu.lower()]
    body={
        "guestAccelerators": [{
            "acceleratorCount": 1,
            "acceleratorType": f"https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/acceleratorTypes/{gpu}"
        },],
    }
    if gpu == None:
        body = {"guestAccelerators": []}

    op = compute.instances().setMachineResources(
        project=project,
        zone=zone,
        instance=instance,
        body=body).execute()
    wait_for_operation(compute, project, zone, op['name'])

def set_ssh_config(compute, project, zone, instance):
    ip = instance_ip(compute, project, zone, instance)
    if ip == None:
        raise Exception(f"{instance} does not have an IP. Is it running?")
    h = (
        f"Host {instance}\n"
        f"  HostName {ip}\n"
        "  ForwardAgent yes\n"
        "  AddKeysToAgent yes\n"
        "  CheckHostIP no\n"
    )

    # delete the old conf
    conf_path = os.path.join(os.environ["HOME"], ".ssh/config")
    ssh_config = ""
    with open(conf_path) as f:
        deleting = False
        for l in f.readlines():
            if f"Host {instance}" in l:
                deleting = True
            elif l.startswith(" ") and deleting:
                # ignore the following lines
                pass
            else:
                deleting = False
                ssh_config += l
    
    # append the conf
    ssh_config = ssh_config.rstrip() + "\n\n" + h

    with open(conf_path, "w") as f:
        f.write(ssh_config)
    print(f"Host {instance} has been added to .ssh/config")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project_id', default="lucid-destiny-223610", help='Your Google Cloud project ID.')
    parser.add_argument('--zone', default="asia-east1-c", help='GCP zone to operate on')
    subparsers = parser.add_subparsers(dest="subcommand")
    
    # ls parser
    ls = subparsers.add_parser('ls')
    # start parser
    start = subparsers.add_parser('start')
    start.add_argument('instance')
    # stop parser
    stop = subparsers.add_parser('stop')
    stop.add_argument('instance')
    # ssh parser
    ssh = subparsers.add_parser('ssh')
    ssh.add_argument('instance')
    # gpu parser
    gpu_parser = subparsers.add_parser('gpu')
    gpu_parser.add_argument('instance')
    gpu_parser.add_argument('gpu', choices=['v100', 't4', 'none'])

    args = parser.parse_args()

    print(f"Project ID: {args.project_id}")
    print(f"Zone: {args.zone}")
    print("---")

    compute = googleapiclient.discovery.build('compute', 'v1')
    if args.subcommand == 'ls':
        list_instances(compute, args.project_id, args.zone)
    elif args.subcommand == 'start':
        start_instance(compute, args.project_id, args.zone, args.instance)
    elif args.subcommand == 'stop':
        stop_instance(compute, args.project_id, args.zone, args.instance)
    elif args.subcommand == 'ssh':
        set_ssh_config(compute, args.project_id, args.zone, args.instance)
    elif args.subcommand == 'gpu':
        set_gpu(compute, args.project_id, args.zone, args.instance, args.gpu)
