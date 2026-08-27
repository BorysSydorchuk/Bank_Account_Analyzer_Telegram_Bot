# S7-08: transactional email for S7-09's verification/reset flows.
# Domain identity for mymble.be, DKIM-signed (Easy DKIM — SES generates
# and manages the signing key, we only publish the three CNAME tokens
# it hands back). No MAIL FROM domain override — SES's default
# amazonses.com MAIL FROM is sufficient for a domain-verified identity
# and keeps this minimal, matching the ticket's own "polish is not the
# goal" instruction.
resource "aws_sesv2_email_identity" "mymble" {
  email_identity = "mymble.be"

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = aws_route53_zone.mymble.zone_id
  name    = "${aws_sesv2_email_identity.mymble.dkim_signing_attributes[0].tokens[count.index]}._domainkey.mymble.be"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_sesv2_email_identity.mymble.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

# SES sandbox (the account's default state until production access is
# granted) requires the RECIPIENT to be verified too, not just the
# sender domain — this is what makes a real end-to-end test possible
# before that approval lands. Borys's own real address, already the one
# this project's AWS Budget alerts go to (infra/budget.tf).
resource "aws_sesv2_email_identity" "test_recipient" {
  email_identity = var.ses_test_recipient_email
}

# S8-02: a second real test recipient, same sandbox-mode reasoning as
# test_recipient above — needed to verify a real beta-style
# registration (a genuinely different person's inbox, not just Borys's
# own) actually receives the verification email while production SES
# access is still denied (see ARCHITECTURE.md's Auth section). Kept as
# its own resource rather than widening ses_test_recipient_email to a
# list, since this is a one-off real test account, not a pattern this
# project needs to scale — S8-05/S8-06 will need a real answer to SES
# sandbox mode before real beta invites work at all, tracked there.
resource "aws_sesv2_email_identity" "liyaberry_test_recipient" {
  email_identity = "liyaberry27@gmail.com"
}

# Grants both web and worker (they share this one task role, same as
# every other ECS-task permission in this project) real sending
# capability with zero credential material anywhere — no access key, no
# Secrets Manager entry, nothing to rotate or leak. boto3 inside the
# container resolves these permissions automatically via the task's
# credential provider chain. Scoped to two identity ARNs, not ses:* —
# a compromised container could send mail as mymble.be, but never as an
# arbitrary verified identity elsewhere in the account.
#
# Real finding, not assumed: while the account is in SES sandbox mode,
# ses:SendEmail's IAM authorization checks BOTH the sender identity and
# the recipient identity ARN — confirmed by an actual AccessDenied error
# naming the recipient's ARN, not the sender's, when this policy only
# granted the domain identity. The test-recipient identity is included
# here for that reason; once production access is granted, sandbox's
# per-recipient verification requirement stops applying to real users,
# but this entry causes no harm left in place — it's still just
# permission to send to one specific, already-real address.
resource "aws_iam_role_policy" "ecs_task_send_email" {
  name = "${var.project_name}-ses-send"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "SendEmail"
      Effect = "Allow"
      Action = ["ses:SendEmail", "ses:SendRawEmail"]
      Resource = [
        aws_sesv2_email_identity.mymble.arn,
        aws_sesv2_email_identity.test_recipient.arn,
        aws_sesv2_email_identity.liyaberry_test_recipient.arn,
      ]
    }]
  })
}
