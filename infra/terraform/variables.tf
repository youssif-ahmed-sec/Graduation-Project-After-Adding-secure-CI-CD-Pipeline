variable "aws_region" {
  description = "AWS Region for the Lightsail instance"
  type        = string
  default     = "eu-central-1"
}

variable "instance_name" {
  description = "Name of the staging Lightsail instance"
  type        = string
  default     = "filetrack-mini-edr-staging"
}

variable "availability_zone" {
  description = "Availability Zone for Lightsail"
  type        = string
  default     = "eu-central-1a"
}

variable "bundle_id" {
  description = "Lightsail instance bundle"
  type        = string
  default     = "small_3_0"
}
