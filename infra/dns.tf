# S7-04: mymble.be is registered externally (not through Route 53) —
# this zone needs NS delegation at that registrar before it's
# authoritative. ACM's DNS validation, and mymble.be actually resolving
# to the ALB, both depend on that delegation being live; neither can be
# verified until Borys completes it.
resource "aws_route53_zone" "mymble" {
  name = "mymble.be"
}

# Alias, not a plain A record with a hardcoded IP — the ALB's IPs can
# change (scaling, AZ failover), an alias record tracks it automatically
# and, unlike a CNAME, is allowed at the zone apex.
resource "aws_route53_record" "apex_alias" {
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "mymble.be"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
