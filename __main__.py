import pulumi
import pulumi_aws as aws
import base64

class Infrastructure(pulumi.ComponentResource):
    def __init__(self, name, ami_id, app_port):
        super().__init__("custom:infrastructure:Infrastructure", name)

        # Create a VPC
        vpc = aws.ec2.Vpc("my-vpc", cidr_block="10.0.0.0/16")
        vpc_id = vpc.id

        # Use 'await' to get availability zones
        available = aws.get_availability_zones(state="available")

        public_subnets = []
        private_subnets = []

        for i, az in enumerate(available.names):
            public_subnet = aws.ec2.Subnet(f"public-subnet-{az}",
                vpc_id=vpc_id,
                availability_zone=az,
                cidr_block=f"10.0.{i + 1}.0/24",
                tags={
                    "Name": f"public-subnet-{az}",
                })
            public_subnets.append(public_subnet)

            private_subnet = aws.ec2.Subnet(f"private-subnet-{az}",
                vpc_id=vpc_id,
                availability_zone=az,
                cidr_block=f"10.0.{i + len(available.names) * 2 + 1}.0/24",
                tags={
                    "Name": f"private-subnet-{az}",
                })
            private_subnets.append(private_subnet)

        # Create an Internet Gateway and associate it with the VPC
        gw = aws.ec2.InternetGateway("gw",
            vpc_id=vpc_id,
            tags={
                "Name": "gateway",
            })

        # Create a public route table and associate public subnets with it
        public_route_table = aws.ec2.RouteTable("public-routes",
            vpc_id=vpc_id,
            routes=[aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=gw.id,
            )],
            tags={
                "Name": "public-routes",
            })

        for i in range(len(public_subnets)):
            aws.ec2.RouteTableAssociation(f"public-route-association-{i}",
                subnet_id=public_subnets[i].id,
                route_table_id=public_route_table.id)

        # Create a private route table and associate private subnets with it
        private_route_table = aws.ec2.RouteTable("private-routes",
            vpc_id=vpc_id,
            tags={
                "Name": "private-routes",
            })

        for i in range(len(private_subnets)):
            aws.ec2.RouteTableAssociation(f"private-route-association-{i}",
                subnet_id=private_subnets[i].id,
                route_table_id=private_route_table.id)



        # Create a security group for the load balancer
        load_balancer_security_group = aws.ec2.SecurityGroup('load_balancer_security_group',
            description='Enable access to the load balancer',
            vpc_id=vpc_id,
        )

        # Ingress rule to allow TCP traffic on port 80 (HTTP)
        load_balancer_security_group_http_ingress = aws.ec2.SecurityGroupRule('load_balancer_security_group_http_ingress',
            type='ingress',
            from_port=80,
            to_port=80,
            protocol='tcp',
            cidr_blocks=['0.0.0.0/0'],
            security_group_id=load_balancer_security_group.id,
        )

        # Ingress rule to allow TCP traffic on port 443 (HTTPS)
        load_balancer_security_group_https_ingress = aws.ec2.SecurityGroupRule('load_balancer_security_group_https_ingress',
            type='ingress',
            from_port=443,
            to_port=443,
            protocol='tcp',
            cidr_blocks=['0.0.0.0/0'],
            security_group_id=load_balancer_security_group.id,
        )

        
        # Create a security group for the application
        # app_security_group = aws.ec2.SecurityGroup("application-security-group",
        #     description="Application Security Group",
        #     vpc_id=vpc_id,
        #     ingress=[
        #         aws.ec2.SecurityGroupIngressArgs(
        #             description="SSH from anywhere",
        #             from_port=22,
        #             to_port=22,
        #             protocol="tcp",
        #             cidr_blocks=["0.0.0.0/0"],
        #         ),
        #         aws.ec2.SecurityGroupIngressArgs(
        #             description="HTTP from anywhere",
        #             from_port=80,
        #             to_port=80,
        #             protocol="tcp",
        #             cidr_blocks=["0.0.0.0/0"],
        #         ),
        #         aws.ec2.SecurityGroupIngressArgs(
        #             description="HTTPS from anywhere",
        #             from_port=443,
        #             to_port=443,
        #             protocol="tcp",
        #             cidr_blocks=["0.0.0.0/0"],
        #         ),
        #         aws.ec2.SecurityGroupIngressArgs(
        #             description=f"YourApplicationPort from anywhere",
        #             from_port=app_port,
        #             to_port=app_port,
        #             protocol="tcp",
        #             cidr_blocks=["0.0.0.0/0"],
        #         ),
        #     ],
        #     egress=[
        #         aws.ec2.SecurityGroupEgressArgs(
        #             from_port=0,
        #             to_port=0,
        #             protocol="-1",
        #             cidr_blocks=["0.0.0.0/0"],
        #         ),
        #     ],
        #     tags={
        #         "Name": "allow_tls",
        #     })
        app_security_group = aws.ec2.SecurityGroup("application-security-group",
            description="Application Security Group",
            vpc_id=vpc_id,
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    description="SSH from load balancer",
                    from_port=22,
                    to_port=22,
                    protocol="tcp", 
                    cidr_blocks=["0.0.0.0/0"],
                ),
                # aws.ec2.SecurityGroupIngressArgs(
                #     description=f"Application traffic from load balancer",
                #     from_port=8081,
                #     to_port=8081,
                #     protocol="tcp",
                #     source_security_group_id= load_balancer_security_group.id,
                #     # security_groups=[load_balancer_security_group.id],
                # ),
            ],
            egress=[
                # aws.ec2.SecurityGroupEgressArgs(
                #     from_port=0,
                #     to_port=0,
                #     protocol="-1",
                #     cidr_blocks=["0.0.0.0/0"],
                # ),

                aws.ec2.SecurityGroupEgressArgs(
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ], 
        )


        

        app_security_group_ingress = aws.ec2.SecurityGroupRule('app_security_group_ingress',
            type='ingress',
            from_port=8081,
            to_port=8081,
            protocol='tcp',
            source_security_group_id=load_balancer_security_group.id,
            security_group_id=app_security_group.id,
            

        )

        load_balancer_security_group_egress = aws.ec2.SecurityGroupRule('load_balancer_security_group_port_egress',
            type='egress',
            from_port=8081,
            to_port=8081,
            protocol='tcp',
            source_security_group_id=app_security_group.id,
            security_group_id=load_balancer_security_group.id,
            

        )


        # Create a security group for the RDS instance
        rds_security_group = aws.ec2.SecurityGroup("database-security-group",
            description="Database Security Group",
            vpc_id=vpc_id,
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    description="MySQL Database Ingress",
                    from_port=3306,
                    to_port=3306,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                    security_groups=[app_security_group.id],
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
            tags={
                "Name": "allow_tls",
            })



        app_security_group_egress = aws.ec2.SecurityGroupRule('app_security_group_egress',
            type='egress',
            from_port=0,
            to_port=3306,
            protocol='tcp',
            source_security_group_id=rds_security_group.id,
            security_group_id=app_security_group.id,
            

        )

        # Create an RDS Parameter Group
        rds_parameter_group = aws.rds.ParameterGroup(
            "rds-parameter-group",
            family="mariadb10.6",
            parameters=[
                {
                    "name": "time_zone",
                    "value": "UTC",
                },
            ]
        )


        # Create an RDS Subnet Group
        rds_subnet_group = aws.rds.SubnetGroup(
            "rds-subnet-group",
            name="my-rds-subnet-group",
            subnet_ids=[private_subnets[0].id, private_subnets[1].id],
            description="My RDS Subnet Group",
        )

        # Create an RDS Instance
        rds_instance = aws.rds.Instance(
            "my-rds-instance",
            allocated_storage=20,
            storage_type="gp2",
            engine="mariadb",
            engine_version="10.6.14",
            instance_class="db.t2.micro",
            username="root",
            password="DBpassword",
            db_subnet_group_name=rds_subnet_group.name,
            publicly_accessible=False,
            skip_final_snapshot=False,
            final_snapshot_identifier="finalsnap10",
            db_name="csye6225",
            parameter_group_name=rds_parameter_group.name,
            vpc_security_group_ids=[rds_security_group.id],
            multi_az=False,
            identifier="my-rds-instance",
        )

        rds_instance_details = pulumi.Output.all(rds_instance.id).apply(lambda args:
            aws.rds.get_instance(db_instance_identifier=args[0])
        )

        # Extract relevant information
        user_data_script = rds_instance_details.apply(lambda details: f"""#!/bin/bash
            
            sudo rm -i /home/clouduser/webapp/.env
            
            DB_HOST=$(echo "{details.endpoint}" | sed 's/:3306//')

            echo "DB_HOST_NAME={details.master_username}" >> /home/clouduser/webapp/.env
            echo "DB_PASSWORD=DBpassword" >> /home/clouduser/webapp/.env
            echo "DB_HOST=$DB_HOST" >> /home/clouduser/webapp/.env
            echo "DB_NAME={details.db_name}" >> /home/clouduser/webapp/.env
            echo "DB_PORT=3306" >> /home/clouduser/webapp/.env

            sudo systemctl daemon-reload
            sudo service appgo start
            sudo ervice appgo status
            sudo systemctl enable appgo
            sudo systemctl start appgo

            wget https://amazoncloudwatch-agent.s3.amazonaws.com/debian/amd64/latest/amazon-cloudwatch-agent.deb
            sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

            sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
            -a fetch-config \
            -m ec2 \
            -c file:/opt/cloudwatch-config.json \
            -s
        """).apply(lambda script:
            pulumi.Output.from_input(script)
                .apply(lambda ud: base64.b64encode(ud.encode()).decode("utf-8"))
        )

       # CloudWatch Agent Role
        cloudwatch_agent_role = aws.iam.Role("cloudwatchAgentRole",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [
                    {
                    "Action": "sts:AssumeRole",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Effect": "Allow",
                    "Sid": ""
                    }
                ]
            }"""
        )


        

        # Attach CloudWatch Agent Policy to the role
        cloudwatch_agent_policy_attachment = aws.iam.RolePolicyAttachment(
            'cloudwatchAgentPolicyAttachment',
            role=cloudwatch_agent_role.name,
            policy_arn='arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy'
        )

        # Create an instance profile using the role
        instance_profile = aws.iam.InstanceProfile("cloudwatchAgentRoleInstanceProfile",
            role=cloudwatch_agent_role.name
        )
          # ec2_instance = aws.ec2.Instance(
        #     "my-ec2-instance",
        #     ami=ami_id,
        #     instance_type="t2.micro",
        #     vpc_security_group_ids=[app_security_group.id],
        #     iam_instance_profile=instance_profile.id,
        #     key_name="ami_new",
        #     subnet_id=public_subnets[0].id,
        #     user_data=user_data_script,
        #     associate_public_ip_address=True,
        #     tags={
        #         "Name": "web-instance",
        #     },
        # )


        # Launch Template
        launch_template = aws.ec2.LaunchTemplate("csye6225_launch_template",
            image_id=ami_id,
            instance_type="t2.micro",
            key_name="ami_new",
            #vpc_security_group_ids=[app_security_group.id],
            iam_instance_profile={
                "name": instance_profile.name
            },
            user_data=user_data_script,
            network_interfaces=[{
                "associate_public_ip_address": True,
                "security_groups": [app_security_group.id],  # Specify the security group ID here
                "subnet_id": public_subnets[0],  # Specify your subnet ID here
            }],
            tag_specifications=[{
                "resourceType": "instance",
                "tags": {
                    "Name": "csye6225_instance",
                    "AutoScalingGroup": "TagProperty"
                }
            }],
        )



        web_target_group = aws.lb.TargetGroup('web-target-group',
            port=8081,
            protocol='HTTP',
            target_type='instance',
            vpc_id=vpc_id,
            health_check=aws.lb.TargetGroupHealthCheckArgs(
                path="/healthz",
                port="8081",
                protocol="HTTP",
                interval=30,
                timeout=10,
                unhealthy_threshold=2,
                healthy_threshold=2,
            )
        )


        # Auto Scaling Group
        asg = aws.autoscaling.Group("csye6225_asg",
            desired_capacity=1,
            min_size=1,
            max_size=3,
            default_cooldown=60,
            vpc_zone_identifiers=public_subnets,
            launch_template={
                "id": launch_template.id,
                "version": "$Latest",
            },
            tags=[
                aws.autoscaling.GroupTagArgs(
                    key="AutoScalingGroup",
                    value="TagProperty",
                    propagate_at_launch=True,
                )
            ],
            target_group_arns=[web_target_group.arn],
        )

        scale_up_policy = aws.autoscaling.Policy("scale_up",
            scaling_adjustment=1,
            adjustment_type="ChangeInCapacity",
            cooldown=60,
            autoscaling_group_name=asg.name,
        )

       # AutoScaling Policies
        cpu_alarm_high = aws.cloudwatch.MetricAlarm("cpu_high",
            comparison_operator="GreaterThanOrEqualToThreshold",
            evaluation_periods=2,
            metric_name="CPUUtilization",
            namespace="AWS/EC2",
            period=60,
            statistic="Average",
            threshold=5,
            alarm_description="CPU usage is too high",
            alarm_actions=[scale_up_policy.arn],
            actions_enabled=True,
            dimensions={
                "AutoScalingGroupName": asg.name,
            },
        )



        scale_down_policy = aws.autoscaling.Policy("scale_down",
            scaling_adjustment=-1,
            adjustment_type="ChangeInCapacity",
            cooldown=60,
            autoscaling_group_name=asg.name,
        )
        cpu_alarm_low = aws.cloudwatch.MetricAlarm("cpu_low",
            comparison_operator="LessThanOrEqualToThreshold",
            evaluation_periods=2,
            metric_name="CPUUtilization",
            namespace="AWS/EC2",
            period=60,
            statistic="Average",
            threshold=3,
            alarm_description="CPU usage is too low",
            alarm_actions=[scale_down_policy.arn],
            actions_enabled=True,
            dimensions={
                "AutoScalingGroupName": asg.name,
            },
        )

       



       
        
        # Create Application Load Balancer
        application_load_balancer = aws.lb.LoadBalancer("AppLoadBalancer", 
            internal=False,
            load_balancer_type="application",
            security_groups=[load_balancer_security_group.id],
            subnets=public_subnets,
        )



        alb_listener = aws.lb.Listener("AlbListener",
            load_balancer_arn=application_load_balancer.arn,
            port=80,
            protocol="HTTP",
            default_actions=[aws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=web_target_group.arn,
            )]
        )


        # Get the existing Route 53 zone
        my_zone = aws.route53.get_zone(name="dev.sripulakanti.com")

        # Import or create the Route 53 record
        try:
            # Try to create a new record
            a_record = aws.route53.Record("aRecord",
                name="dev.sripulakanti.com",
                type="A",
                zone_id=my_zone.zone_id,
                aliases=[
                    aws.route53.RecordAliasArgs(
                        name=application_load_balancer.dns_name,
                        zone_id=application_load_balancer.zone_id,
                        evaluate_target_health=True,
                    )
                ]
            )
        except pulumi.ResourceError as e:
            if "Tried to create resource record set" in str(e):
                # The record already exists, import it
                a_record = aws.route53.Record.get("aRecord",
                    name="dev.sripulakanti.com",
                    type="A",
                    zone_id=my_zone.zone_id,
                )
            else:
                # Re-raise the error if it's not the expected error
                raise e
        # my_zone = aws.route53.get_zone(name="dev.sripulakanti.com")

        # a_record = aws.route53.Record("aRecord",
        #     name="dev.sripulakanti.com",
        #     type="A",
        #     zone_id=my_zone.zone_id,
        #     aliases=[
        #         aws.route53.RecordAliasArgs(
        #             name=application_load_balancer.dns_name,
        #             zone_id=application_load_balancer.zone_id,
        #             evaluate_target_health=True,
        #         )
        #     ]
        # )

        # ec2_instance = aws.ec2.Instance(
        #     "my-ec2-instance",
        #     ami=ami_id,
        #     instance_type="t2.micro",
        #     vpc_security_group_ids=[app_security_group.id],
        #     iam_instance_profile=instance_profile.id,
        #     key_name="ami_new",
        #     subnet_id=public_subnets[0].id,
        #     user_data=user_data_script,
        #     associate_public_ip_address=True,
        #     tags={
        #         "Name": "web-instance",
        #     },
        # )



        # a_record = aws.route53.Record('a-record',
        #     zone_id = 'Z08034463W4S7YQ85FZXX', 
        #     name = 'dev.sripulakanti.com',
        #     type = 'A',
        #     ttl = '60',
        #     records = [ec2_instance.public_ip],
        # )

        self.vpc_id = vpc_id
        self.app_security_group_id = app_security_group.id
        #self.ec2_instance_id = pulumi.Output.secret(ec2_instance.id)
        self.rds_security_group_id = rds_security_group.id
        self.rds_instance_endpoint = rds_instance.endpoint
        #self.ec2_launch_template_id = ec2_instance.id

        # Export the values
        # pulumi.export('ec2_launch_template_id', self.ec2_launch_template_id)
        pulumi.export('vpc_id', self.vpc_id)
        pulumi.export('app_security_group_id', self.app_security_group_id)
        #pulumi.export('ec2_instance_id', self.ec2_instance_id)
        pulumi.export('rds_security_group_id', self.rds_security_group_id)
        pulumi.export('rds_instance_endpoint', self.rds_instance_endpoint)

if __name__ == "__main__":
    infrastructure = Infrastructure("my-infrastructure", "ami-0fa84286fef9e7e52", 8081)


