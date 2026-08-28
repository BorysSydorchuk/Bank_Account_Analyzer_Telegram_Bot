# S8-05: DNS records Resend's dashboard generated for mymble.be, added
# here so the domain-verification step is real, applied infrastructure —
# not a manual one-off change nobody else can see or reproduce. Same
# reasoning as ses.tf's now-unused DKIM CNAMEs: the actual record values
# come from the vendor's own dashboard (Borys, since Resend's API key
# used elsewhere in this repo is scoped to sending only, confirmed by a
# real API call — it can't read domain/DNS status), not invented here.

resource "aws_route53_record" "resend_dkim" {
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "resend._domainkey.mymble.be"
  type    = "TXT"
  ttl     = 3600
  records = ["p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDeGZVmQWvdBKQ76flQQIDRy2VmZ9DdpAtKfTyArTP3CeuqyARKkuEUGs/zzTrRqc0F1sZyH+eO/OI8jiguVcNJheGx/gKYEOj5nJ3RDQgkuS9r+gyMun9gmANNs4CaoCPgsJUDT5tvcrDJaL6qQ4FVcBFFMEaPUvqR1lhV4dqI1QIDAQAB"]
}

# Resend's own sending infrastructure — two CNAMEs, labelled "SPF" in its
# dashboard but implemented as CNAME delegation to Resend's MTA rather
# than a bare SPF TXT record.
resource "aws_route53_record" "resend_spf_rsend" {
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "rsend.mymble.be"
  type    = "CNAME"
  ttl     = 3600
  records = ["rsend-euw1.forge.rmta.net"]
}

resource "aws_route53_record" "resend_spf_send" {
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "send.mymble.be"
  type    = "CNAME"
  ttl     = 3600
  records = ["send.forge.rmta.net"]
}

# Optional per Resend's own dashboard, added anyway — real deliverability/
# anti-spoofing practice, and Resend already generated the exact value.
# p=none: report-only, doesn't reject or quarantine misaligned mail — the
# conservative starting point until real DMARC reports are reviewed.
resource "aws_route53_record" "resend_dmarc" {
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "_dmarc.mymble.be"
  type    = "TXT"
  ttl     = 3600
  records = ["v=DMARC1; p=none;"]
}
