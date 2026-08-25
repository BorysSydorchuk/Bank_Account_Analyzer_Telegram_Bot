# S7-04: the one legitimate place for a 0.0.0.0/0 security group rule in
# this whole architecture — everything else (RDS, Redis, the app tier
# itself) is locked to the app SG. This is the actual internet-facing
# edge.
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "Public ALB, inbound 80/443 from the internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP (redirects to HTTPS once the cert is issued)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# The app SG's own ingress list doesn't yet allow traffic from the ALB —
# add it here rather than editing security_groups.tf, since this rule
# only makes sense once the ALB exists.
resource "aws_security_group_rule" "app_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb.id
  description              = "Web service port 8000, from the ALB only"
}

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "web" {
  name        = "${var.project_name}-web"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    # 200 only — a 503 (DB unreachable, CLAUDE.md's structured error
    # response) should correctly mark the target unhealthy so the ALB
    # stops routing to it, same as any other real outage. AWS also
    # rejects 503 in this field outright (health check matchers are
    # restricted to 200-499).
    matcher = "200"
  }
}

# Temporary: HTTP only, forwards directly. Becomes a redirect-to-HTTPS
# once the ACM cert is issued (blocked on Borys completing the mymble.be
# NS delegation — see infra/dns.tf) and a :443 listener is added.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}
