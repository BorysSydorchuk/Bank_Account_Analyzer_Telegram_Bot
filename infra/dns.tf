# S7-04: mymble.be is registered externally (not through Route 53) —
# this zone needs NS delegation at that registrar before it's
# authoritative. ACM's DNS validation, and mymble.be actually resolving
# to the ALB, both depend on that delegation being live; neither can be
# verified until Borys completes it.
resource "aws_route53_zone" "mymble" {
  name = "mymble.be"
}
