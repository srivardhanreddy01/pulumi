import pulumi
import pulumi_aws as aws

def create_vpc_and_subnets():
    # Create a VPC
    vpc = aws.ec2.Vpc("my-vpc", cidr_block="10.0.0.0/16")
    vpcId = vpc.id

    # Use 'await' to get availability zones
    available =  aws.get_availability_zones(state="available")

    public_subnets = []
    private_subnets = []

    for i, az in enumerate(available.names):
        public_subnet = aws.ec2.Subnet(f"public-subnet-{az}",
            vpc_id=vpcId,
            availability_zone=az,
            cidr_block=f"10.0.{i + 1}.0/24",
            tags={
                "Name": f"public-subnet-{az}",
            })
        public_subnets.append(public_subnet)

        private_subnet = aws.ec2.Subnet(f"private-subnet-{az}",
            vpc_id=vpcId,
            availability_zone=az,
            cidr_block=f"10.0.{i + len(available.names)*2 + 1}.0/24",
            tags={
                "Name": f"private-subnet-{az}",
            })
        private_subnets.append(private_subnet)

    # Create an Internet Gateway and associate it with the VPC
    gw = aws.ec2.InternetGateway("gw",
        vpc_id=vpcId,
        tags={
            "Name": "gateway",
        })

    # Create a public route table and associate public subnets with it
    public_route_table = aws.ec2.RouteTable("public-routes",
        vpc_id=vpcId,
        routes=[ aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=gw.id,)
        ],
        tags={
            "Name": "public-routes",
        })

    for i in range(len(public_subnets)):
        aws.ec2.RouteTableAssociation(f"public-route-association-{i}",
            subnet_id=public_subnets[i].id,
            route_table_id=public_route_table.id)

    # Create a private route table and associate private subnets with it
    private_route_table = aws.ec2.RouteTable("private-routes",
        vpc_id=vpcId,
        tags={
            "Name": "private-routes",
        })

    for i in range(len(private_subnets)):
        aws.ec2.RouteTableAssociation(f"private-route-association-{i}",
            subnet_id=private_subnets[i].id,
            route_table_id=private_route_table.id)

    # Export the VPC ID
    pulumi.export('vpc_id', vpc.id)

pulumi_program = create_vpc_and_subnets()
