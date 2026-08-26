# S7-04: real HTTPS for mymble.be, now that NS delegation to the
# infra/dns.tf zone is confirmed live (independently verified via
# nslookup against Google/Cloudflare/OpenDNS resolvers, all agreeing on
# the four Route 53 nameservers — not just trusted on Borys's say-so).
resource "aws_acm_certificate" "mymble" {
  domain_name       = "mymble.be"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation: ACM tells us what CNAME record to create, we create it
# in the zone we control, ACM's own validation checker polls for it —
# no manual "click a link in an email" step, and it survives cert
# renewal automatically (unlike email validation).
resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.mymble.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = aws_route53_zone.mymble.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

# Blocks apply until ACM actually confirms the validation record was
# found and the cert moved to ISSUED — not just "we created the CNAME
# and hope it worked."
resource "aws_acm_certificate_validation" "mymble" {
  certificate_arn         = aws_acm_certificate.mymble.arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}
