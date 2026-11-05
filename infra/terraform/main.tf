provider "aws" {
  region = var.aws_region
}

resource "aws_lightsail_instance" "filetrack_staging" {
  name              = var.instance_name
  availability_zone = var.availability_zone
  blueprint_id      = "ubuntu_24_04"
  bundle_id         = var.bundle_id

  tags = {
    Project     = "FileTrack-Mini-EDR"
    Environment = "staging"
    ManagedBy   = "Terraform"
  }
}
